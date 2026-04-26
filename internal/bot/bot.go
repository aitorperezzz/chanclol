package bot

import (
	"chanclol/internal/common"
	"chanclol/internal/riotapi"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/bwmarrin/discordgo"
	"github.com/rs/zerolog/log"
)

type Guild struct {
	id                  string                           // id of the guild as handled by the discord library
	channelId           string                           // channel where in game messages will be sent
	lastInformedGameIds map[riotapi.Puuid]riotapi.GameId // map with last game ids informed for each player in the guild
}

type Player struct {
	id         riotapi.Puuid    // puuid of the player as handled by riot
	StopWatch  common.Stopwatch // a stopwatch that decides when to check the in game status
	lastOnline time.Time        // last time this player was seen online
}

// Check if the timeout has been reached for this player,
// depending on the player being online or offline.
// Return true if the status has changed (from online to offline or viceversa)
// and false otherwise
func (player *Player) UpdateCheckTimeout(online bool, offlineThreshold time.Duration, onlineTimeout time.Duration, offlineTimeout time.Duration) bool {

	currentTime := time.Now()
	if online {
		player.lastOnline = currentTime
		if player.StopWatch.Timeout != onlineTimeout {
			player.StopWatch.Timeout = onlineTimeout
			return true
		}
	} else {
		if currentTime.Sub(player.lastOnline) > offlineThreshold {
			if player.StopWatch.Timeout != offlineTimeout {
				player.StopWatch.Timeout = offlineTimeout
				return true
			}
		}
	}
	return false
}

type Guilds map[string]*Guild
type Players map[riotapi.Puuid]*Player

type Bot struct {
	token                       string
	database                    DatabaseBot
	mu                          *sync.RWMutex
	riotapi                     *riotapi.RiotApi
	guilds                      Guilds
	players                     Players
	riotapiHousekeepingExecutor common.TimedExecutor
	offlineThreshold            time.Duration
	offlineTimeout              time.Duration
	onlineTimeout               time.Duration
	mainCycle                   time.Duration
	discordgo                   *discordgo.Session
}

func NewBot(
	token string,
	dbFilename string,
	riotapiHousekeepingTimeout time.Duration,
	offlineThreshold time.Duration,
	offlineTimeout time.Duration,
	onlineTimeout time.Duration,
	mainCycle time.Duration,
	riotapi *riotapi.RiotApi) (Bot, error) {

	var bot Bot

	bot.token = token
	// Database
	bot.database = NewDatabaseBot(dbFilename)
	bot.mu = &sync.RWMutex{}
	// Initialise values from the database if present
	bot.guilds = bot.database.GetGuilds()
	bot.players = bot.database.GetPlayers()
	// Housekeeping for the riot API
	bot.riotapiHousekeepingExecutor = common.NewTimedExecutor(riotapiHousekeepingTimeout, bot.riotapiHousekeeping)
	// Timeouts for online and offline players
	bot.offlineThreshold = offlineThreshold
	bot.offlineTimeout = offlineTimeout
	bot.onlineTimeout = onlineTimeout
	// Set default (offline) timeouts for all players
	for _, player := range bot.players {
		player.StopWatch.Timeout = offlineTimeout
	}
	// Main loop cycle
	bot.mainCycle = mainCycle
	// Riot API
	bot.riotapi = riotapi

	return bot, nil

}

func connectWithRetry(dg *discordgo.Session) {

	// This is executed only when the application first starts, and attempts connection
	// to the discord gateway repeatedly until the connection is first established. After that,
	// supposedly the discordgo package will keep the connection alive and retry connections
	log.Info().Msg("Attempting connection to the Discord gateway")
	for {
		err := dg.Open()
		if err == nil {
			log.Info().Msg("Connected to Discord gateway successfully")
			return
		}

		log.Warn().Msg(fmt.Sprintf("Discord connection failed: %v. Retrying in 10s...", err))
		time.Sleep(10 * time.Second)
	}
}

func (bot *Bot) Run() error {
	// Create session
	var err error
	bot.discordgo, err = discordgo.New("Bot " + bot.token)
	if err != nil {
		return fmt.Errorf("could not create discord session")
	}

	// Event handler
	bot.discordgo.AddHandler(bot.Receive)

	// Open session
	connectWithRetry(bot.discordgo)
	defer bot.discordgo.Close()

	// keep bot running until there is an OS interruption
	log.Info().Msg("Running")
	go bot.loop()

	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	<-c

	return nil
}

func (bot *Bot) Receive(discord *discordgo.Session, message *discordgo.MessageCreate) {

	// Reject my own messages
	if message.Author.ID == discord.State.User.ID {
		log.Debug().Msg("Rejecting my own message")
		return
	}

	// Ignore messages from private channels
	if message.GuildID == "" {
		log.Info().Msg("Ignoring private message")
		content := "For the time being, I am ignoring private messages"
		bot.sendResponsesToChannel([]Response{ResponseString{content}}, message.ChannelID)
		return
	}

	// Parse the input provided and call the appropriate function
	log.Debug().Msg(fmt.Sprintf("Received message: %s", message.Content))
	parseResult := Parse(message.Content)

	switch parseResult.parseid {
	case PARSEID_NO_BOT_PREFIX:
		log.Debug().Msg("Rejecting message not intended for the bot")
		return
	case PARSEID_OK:
		log.Info().Msg(fmt.Sprintf("Command understood: %s", message.Content))
		var responses []Response

		// Extract the name of the channel that has sent the message
		channelName, err := bot.getChannelName(discord, message.GuildID, message.ChannelID)
		if err != nil {
			log.Error().Msg(fmt.Sprintf("Could not extract channel name for channel id %s", message.ChannelID))
			return
		}

		// Register the guild if it's the first time I see it
		if bot.addGuildIfMissing(message.GuildID, message.ChannelID) {
			log.Info().Msg(fmt.Sprintf("Initialising guild %s", message.GuildID))
			// Send welcome message
			log.Info().Msg("Sending welcome message")
			responses = append(responses, Welcome(channelName)...)
		}

		// If this is an old guild, take the opportunity to check if the
		// configured channel still exists. If it does not, update the channel
		// and notify
		configuredChannelId, ok := bot.guildChannelId(message.GuildID)
		if !ok {
			log.Error().Msg(fmt.Sprintf("Could not find guild %s after initialisation", message.GuildID))
			return
		}
		configuredChannelName, err := bot.getChannelName(discord, message.GuildID, configuredChannelId)
		if err != nil {
			bot.setGuildChannel(message.GuildID, message.ChannelID)
			configuredChannelName = channelName
			log.Info().Msg(fmt.Sprintf("Updated the channel for in-game messages to %s", channelName))
			responses = append(responses, ChannelDisappeared(channelName)...)
		}

		// Decide according to the command
		switch parseResult.command {
		case COMMAND_REGISTER:
			switch riotid := parseResult.arguments.(type) {
			default:
				panic(fmt.Sprintf("unexpected type of riot id %T", riotid))
			case riotapi.RiotId:
				responses = append(responses, bot.register(riotid, message.GuildID)...)
			}
		case COMMAND_UNREGISTER:
			switch riotid := parseResult.arguments.(type) {
			default:
				panic(fmt.Sprintf("unexpected type of riot id %T", riotid))
			case riotapi.RiotId:
				responses = append(responses, bot.unregister(riotid, message.GuildID)...)
			}
		case COMMAND_RANK:
			switch riotid := parseResult.arguments.(type) {
			default:
				panic(fmt.Sprintf("unexpected type of riot id %T", riotid))
			case riotapi.RiotId:
				responses = append(responses, bot.rank(riotid)...)
			}
		case COMMAND_CHANNEL:
			switch channelName := parseResult.arguments.(type) {
			default:
				panic(fmt.Sprintf("unexpected type of channel name %T", channelName))
			case string:
				responses = append(responses, bot.channel(discord, channelName, message.GuildID)...)
			}
		case COMMAND_STATUS:
			responses = append(responses, bot.status(discord, message.GuildID, configuredChannelName)...)
		case COMMAND_HELP:
			responses = append(responses, HelpMessage()...)
		default:
			panic(fmt.Sprintf("Command %d is not one of the possible ones", parseResult.command))
		}
		bot.sendResponsesToChannel(responses, message.ChannelID)
	default:

		// The command is invalid input, so it contains an error message
		errorMessage := parseResult.errorMessage
		log.Info().Msg(fmt.Sprintf("Wrong input: '%s'. Reason: %s", message.Content, errorMessage))
		bot.sendResponsesToChannel(InputNotValid(errorMessage), message.ChannelID)
	}
}

func (bot *Bot) sendResponsesToChannel(responses []Response, channelId string) {
	for _, response := range responses {
		response.Send(channelId, bot.discordgo)
	}
}

// When sending responses to a guild, find the channel id configured
// for the guild, and send the responses to that channel
func (bot *Bot) sendResponsesToGuild(responses []Response, guildid string) {

	// Get the channel id for this guild
	channelid, ok := bot.guildChannelId(guildid)
	if !ok {
		log.Warn().Msg(fmt.Sprintf("Could not send response because guild %s is not registered", guildid))
		return
	}
	bot.sendResponsesToChannel(responses, channelid)
}

func (bot *Bot) register(riotid riotapi.RiotId, guildid string) []Response {

	// Get the puuid
	puuid, err := bot.riotapi.GetPuuid(riotid)
	if err != nil {
		log.Info().Err(err)
		return NoResponseRiotApi(riotid)
	}

	// Check if player already belongs to the guild
	if bot.isPlayerRegisteredInGuild(puuid, guildid) {
		log.Info().Msg(fmt.Sprintf("Player %s is already registered in guild %s", riotid, guildid))
		return PlayerAlreadyRegistered(riotid)
	}

	// Get rank of this player
	leagues, err := bot.riotapi.GetLeagues(puuid)
	if err != nil {
		log.Info().Err(err)
		return NoResponseRiotApi(riotid)
	}

	// Now it's safe to register the player
	log.Info().Msg(fmt.Sprintf("Registering player %s in guild %s", &riotid, guildid))
	if !bot.addPlayerToGuild(puuid, guildid) {
		log.Info().Msg(fmt.Sprintf("Player %s is already registered in guild %s", riotid, guildid))
		return PlayerAlreadyRegistered(riotid)
	}

	// Send the final message
	log.Info().Msg(fmt.Sprintf("Player %s has been registered in guild %s", &riotid, guildid))
	return []Response{
		PlayerRegistered(riotid),
		PlayerRank(riotid, leagues),
	}
}

func (bot *Bot) unregister(riotid riotapi.RiotId, guildid string) []Response {

	// Get the puuid
	puuid, err := bot.riotapi.GetPuuid(riotid)
	if err != nil {
		log.Info().Err(err)
		return NoResponseRiotApi(riotid)
	}

	// Check if the player was registered in the guild
	if !bot.isPlayerRegisteredInGuild(puuid, guildid) {
		log.Info().Msg(fmt.Sprintf("Player %s was not previously registered in guild %s", riotid, guildid))
		return PlayerNotPreviouslyRegistered(riotid)
	}

	// Check if the player was registered in the guild
	log.Info().Msg(fmt.Sprintf("Unregistering player %s from guild id %s", riotid, guildid))
	removedFromGuild, removedCompletely := bot.removePlayerFromGuild(puuid, guildid)
	if !removedFromGuild {
		log.Info().Msg(fmt.Sprintf("Player %s was not previously registered in guild %s", riotid, guildid))
		return PlayerNotPreviouslyRegistered(riotid)
	}
	log.Info().Msg(fmt.Sprintf("Player %s has been unregistered from guild %s", riotid, guildid))
	// If the player does not belong to ANY guild, remove it completely
	if removedCompletely {
		log.Info().Msg(fmt.Sprintf("Player %s removed completely", riotid))
	}
	return PlayerUnregistered(riotid)
}

func (bot *Bot) rank(riotid riotapi.RiotId) []Response {

	// Get the puuid
	puuid, err := bot.riotapi.GetPuuid(riotid)
	if err != nil {
		log.Info().Err(err)
		return NoResponseRiotApi(riotid)
	}

	// Get the rank of this player
	leagues, err := bot.riotapi.GetLeagues(puuid)
	if err != nil {
		log.Info().Err(err)
		return NoResponseRiotApi(riotid)
	}

	// Send the final message
	log.Info().Msg(fmt.Sprintf("Sending rank of player %s", riotid))
	return []Response{PlayerRank(riotid, leagues)}
}

func (bot *Bot) channel(discord *discordgo.Session, channelName string, guildid string) []Response {

	// Try to find the id from the channel name
	channelId, err := bot.getChannelId(discord, guildid, channelName)
	if err != nil {
		log.Info().Msg(fmt.Sprintf("Could not extract channel id from channel name %s", channelName))
		return ChannelDoesNotExist(channelName)
	}

	// We have a new channel to send messages to
	log.Info().Msg(fmt.Sprintf("Changing channel used by guild %s to %s", guildid, channelName))
	bot.setGuildChannel(guildid, channelId)
	return ChannelChanged(channelName)
}

func (bot *Bot) status(discord *discordgo.Session, guildid string, configuredChannelName string) []Response {

	// Create list of player names in this guild
	riotIds := []riotapi.RiotId{}
	for _, puuid := range bot.guildPuuids(guildid) {
		riotid, err := bot.riotapi.GetRiotId(puuid)
		if err != nil {
			panic(err)
		}
		riotIds = append(riotIds, riotid)
	}
	return StatusMessage(riotIds, configuredChannelName)
}

func (bot *Bot) loop() {

	for {
		// TODO: investigate if this wait time needs to be updated according to
		// the number of users registered
		var wg sync.WaitGroup
		wg.Add(1)
		go func() {
			defer wg.Done()
			time.Sleep(bot.mainCycle)
		}()
		wg.Wait()
		// Housekeeping of the Riot API if necessary
		bot.riotapiHousekeepingExecutor.Execute()
		// Find a player to check during this iteration
		puuid, found := bot.selectPlayerToCheck()
		if !found {
			continue
		}
		riotid, err := bot.riotapi.GetRiotId(puuid)
		if err != nil {
			log.Error().Err(err)
			continue
		}
		// We have a player to check
		log.Debug().Msg(fmt.Sprintf("Checking in game status of player %s", riotid))
		spectator, err := bot.riotapi.GetSpectator(puuid)
		// At this point, a request has been performed in some form,
		// so the stopwatch needs to be reset
		if !bot.startPlayerStopwatch(puuid) {
			continue
		}
		if err != nil {
			if errors.Is(err, common.ErrNotFound) {
				log.Debug().Msg(fmt.Sprintf("Spectator data for player %s is not available", riotid))
				if bot.updatePlayerCheckTimeout(puuid, false) {
					log.Info().Msg(fmt.Sprintf("Player %s is now offline", riotid))
				}
			} else {
				log.Warn().Err(err).Msg(fmt.Sprintf("Could not check spectator data for player %s", riotid))
			}
			continue
		}
		// Player is online, update timeout if needed
		if bot.updatePlayerCheckTimeout(puuid, true) {
			log.Info().Msg(fmt.Sprintf("Player %s is now online", &riotid))
		}
		// Get the guilds where this player is registered
		for _, target := range bot.guildNotificationTargets(puuid, spectator.GameId) {
			log.Info().Msg(fmt.Sprintf("Sending spectator message for player %s and game %d in guild %s", &riotid, spectator.GameId, target.guildid))
			// Build the complete response
			responses := InGameMessage(puuid, riotid, spectator)
			bot.sendResponsesToChannel(responses, target.channelid)
			// Update last informed game id
			bot.setLastInformedGameId(puuid, target.guildid, spectator.GameId)
		}
	}
}

func (bot *Bot) selectPlayerToCheck() (riotapi.Puuid, bool) {

	log.Debug().Msg("Selecting player to check in this iteration")
	var longestTimeStopped time.Duration
	var puuid riotapi.Puuid
	for _, player := range bot.playerCheckStates() {
		riotid, err := bot.riotapi.GetRiotId(player.puuid)
		if err != nil {
			panic(err)
		}
		// Time the stopwatch has been stopped for this player
		if player.stopped {
			if player.elapsed > longestTimeStopped {
				// This player is available to be checked,
				// and has been stopped more than the others,
				// so it's our best candidate
				log.Debug().Msg(fmt.Sprintf("- %s: player has been stopped for longer", &riotid))
				longestTimeStopped = player.elapsed
				puuid = player.puuid
			} else {
				// This player is available to check, but has been checked
				// more recently than others
				log.Debug().Msg(fmt.Sprintf("- %s: player has been checked more recently", &riotid))
			}
		} else {
			log.Debug().Msg(fmt.Sprintf("- %s: timeout still not reached", &riotid))
		}
	}
	// We have selected the best option to check
	if puuid == "" {
		log.Debug().Msg("Not checking any player during this iteration")
		return puuid, false
	} else {
		log.Debug().Msg(fmt.Sprintf("Checking player with puuid %s in this iteration", puuid))
		return puuid, true
	}
}

// Get channel name, provided a channel id, from the discord api
func (bot *Bot) getChannelName(discord *discordgo.Session, guildid string, channelid string) (string, error) {

	channels, err := discord.GuildChannels(guildid)
	if err != nil {
		return "", fmt.Errorf("could not extract list of channels of guild id %s", guildid)
	}
	for _, ch := range channels {
		if ch.ID == channelid {
			return ch.Name, nil
		}
	}
	return "", fmt.Errorf("no channel name found for channel id %s", channelid)
}

func (bot *Bot) getChannelId(discord *discordgo.Session, guildid string, channelName string) (string, error) {

	channels, err := discord.GuildChannels(guildid)
	if err != nil {
		return "", fmt.Errorf("could not extract list of channels of guild id %s", guildid)
	}
	for _, ch := range channels {
		if ch.Name == channelName {
			return ch.ID, nil
		}
	}
	return "", fmt.Errorf("no channel id found for channel name %s", channelName)
}

func (bot *Bot) riotapiHousekeeping() {
	log.Info().Msg("Performing Riot API housekeeping")
	bot.riotapi.Housekeeping(bot.registeredPuuids())
}
