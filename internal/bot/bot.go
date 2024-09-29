package bot

import (
	"chanclol/internal/common"
	"chanclol/internal/riotapi"
	"fmt"
	"os"
	"os/signal"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"
)

type Guild struct {
	id                  string
	channelId           string
	lastInformedGameIds map[riotapi.Puuid]riotapi.GameId
}

type Player struct {
	id         riotapi.Puuid
	StopWatch  common.Stopwatch
	lastOnline time.Time
}

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

func CreateBot(token string, dbFilename string, riotapiHousekeepingTimeout time.Duration, offlineThreshold time.Duration, offlineTimeout time.Duration, onlineTimeout time.Duration, mainCycle time.Duration, riotapi *riotapi.RiotApi) (Bot, error) {

	var bot Bot

	bot.token = token
	// Database
	bot.database = CreateDatabaseBot(dbFilename)
	// Initialise values from the database if present
	bot.guilds = bot.database.GetGuilds()
	bot.players = bot.database.GetPlayers()
	// Housekeeping for the riot API
	bot.riotapiHousekeepingExecutor = common.CreateTimedExecutor(riotapiHousekeepingTimeout, bot.riotapiHousekeeping)
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
	fmt.Println("Opening discord session")
	bot.discordgo.Open()
	defer bot.discordgo.Close()

	// keep bot running untill there is NO os interruption (ctrl + C)
	fmt.Println("Running")
	bot.loop()
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt)
	<-c

	return nil
}

func (bot *Bot) Receive(discord *discordgo.Session, message *discordgo.MessageCreate) {

	// Reject my own messages
	if message.Author.ID == discord.State.User.ID {
		fmt.Println("Rejecting my own message")
		return
	}

	// Ignore messages from private channels
	if message.GuildID == "" {
		fmt.Println("Ignoring private message")
		content := "For the time being, I am ignoring private messages"
		bot.sendResponsesToChannel([]Response{ResponseString{content}}, message.ChannelID)
		return
	}

	// Register the guild if it's the first time I see it
	if _, ok := bot.guilds[message.GuildID]; !ok {
		fmt.Printf("Initialising guild %s\n", message.GuildID)
		guild := Guild{id: message.GuildID, channelId: message.ChannelID}
		guild.lastInformedGameIds = make(map[riotapi.Puuid]riotapi.GameId)
		bot.guilds[message.GuildID] = &guild
		bot.database.AddGuild(message.GuildID, message.ChannelID)
		fmt.Println("Sending welcome message")

		// extract the name of the channel
		channelName, err := bot.getChannelName(discord, message.GuildID, message.ChannelID)
		if err != nil {
			fmt.Printf("Could not extract channel name for channel id %s\n", message.ChannelID)
			return
		}

		// Send welcome message
		bot.sendResponsesToChannel(Welcome(channelName), message.ChannelID)
	}
	guild := bot.guilds[message.GuildID]

	// Parse the input provided and call the appropriate function
	fmt.Printf("Received message: %s\n", message.Content)
	parseResult := Parse(message.Content)
	switch parseResult.parseid {
	case PARSEID_NO_BOT_PREFIX:
		fmt.Println("Rejecting message not intended for the bot")
		return
	case PARSEID_OK:
		fmt.Printf("Command understood: %s\n", message.Content)
		var responses []Response
		switch parseResult.command {
		case COMMAND_REGISTER:
			switch riotid := parseResult.arguments.(type) {
			default:
				panic(fmt.Sprintf("unexpected type of riot id %T", riotid))
			case riotapi.RiotId:
				responses = bot.register(riotid, guild)
			}
		case COMMAND_UNREGISTER:
			switch riotid := parseResult.arguments.(type) {
			default:
				panic(fmt.Sprintf("unexpected type of riot id %T", riotid))
			case riotapi.RiotId:
				responses = bot.unregister(riotid, guild)
			}
		case COMMAND_RANK:
			switch riotid := parseResult.arguments.(type) {
			default:
				panic(fmt.Sprintf("unexpected type of riot id %T", riotid))
			case riotapi.RiotId:
				responses = bot.rank(riotid)
			}
		case COMMAND_CHANNEL:
			switch channelName := parseResult.arguments.(type) {
			default:
				panic(fmt.Sprintf("unexpected type of channel name %T", channelName))
			case string:
				responses = bot.channel(discord, channelName, guild)
			}
		case COMMAND_STATUS:
			responses = bot.status(discord, guild)
		case COMMAND_HELP:
			responses = HelpMessage()
		default:
			panic(fmt.Sprintf("Command %d is not one of the possible ones", parseResult.command))
		}
		bot.sendResponsesToChannel(responses, message.ChannelID)
	default:

		// The command is invalid input, so it contains an error message
		errorMessage := parseResult.errorMessage
		fmt.Printf("Wrong input: '%s'. Reason: %s\n", message.Content, errorMessage)
		bot.sendResponsesToChannel(InputNotValid(errorMessage), message.ChannelID)
	}
}

func (bot *Bot) sendResponsesToChannel(responses []Response, channelId string) {
	for _, response := range responses {
		response.Send(channelId, bot.discordgo)
	}
}

func (bot *Bot) sendResponsesToGuild(responses []Response, guildid string) {

	// Get the channel id for this guild
	bot.sendResponsesToChannel(responses, bot.guilds[guildid].channelId)
}

func (bot *Bot) register(riotid riotapi.RiotId, guild *Guild) []Response {

	// Get the puuid
	puuid, err := bot.riotapi.GetPuuid(riotid)
	if err != nil {
		fmt.Printf("Puuid not found for riot id %s\n", &riotid)
		return NoResponseRiotApi(riotid)
	}

	// Check if player already belongs to the guild
	if _, ok := guild.lastInformedGameIds[puuid]; ok {
		fmt.Printf("Player %s is already registered in guild %s\n", riotid, guild.id)
		return PlayerAlreadyRegistered(riotid)
	}

	// Get rank of this player
	leagues, err := bot.riotapi.GetLeagues(puuid)
	if err != nil {
		fmt.Printf("Could not get rank from Riot API for player %s\n", &riotid)
	}

	// Now it's safe to register the player
	fmt.Printf("Registering player %s in guild %s\n", &riotid, guild.id)
	// Add it to my complete list of players if necessary
	if _, ok := bot.players[puuid]; !ok {
		player := Player{id: puuid}
		player.StopWatch.Timeout = bot.offlineTimeout
		bot.players[puuid] = &player
	}
	// Add to the guild
	guild.lastInformedGameIds[puuid] = 0
	// Add to the database
	bot.database.AddPlayerToGuild(puuid, guild.id)

	// Send the final message
	fmt.Printf("Player %s has been registered in guild %s\n", &riotid, guild.id)
	return []Response{
		PlayerRegistered(riotid),
		PlayerRank(riotid, leagues),
	}
}

func (bot *Bot) unregister(riotid riotapi.RiotId, guild *Guild) []Response {

	// Get the puuid
	puuid, err := bot.riotapi.GetPuuid(riotid)
	if err != nil {
		fmt.Printf("Could not find a puuid for riot id %s\n", riotid)
		return NoResponseRiotApi(riotid)
	}

	// Check if the player was registered in the guild
	if _, ok := guild.lastInformedGameIds[puuid]; !ok {
		fmt.Printf("Player %s was not previously registered in guild %s\n", riotid, guild.id)
		return PlayerNotPreviouslyRegistered(riotid)
	}

	// Check if the player was registered in the guild
	fmt.Printf("Unregistering player %s from guild id %s\n", riotid, guild.id)
	delete(guild.lastInformedGameIds, puuid)
	// Remove from the database
	bot.database.RemovePlayerFromGuild(puuid, guild.id)
	fmt.Printf("Player %s has been unregistered from guild %s\n", riotid, guild.id)
	// If the player does not belong to ANY guild, remove it completely
	if len(bot.getGuildIds(puuid)) == 0 {
		delete(bot.players, puuid)
		fmt.Printf("Player %s removed completely\n", riotid)
	}
	return PlayerUnregistered(riotid)
}

func (bot *Bot) rank(riotid riotapi.RiotId) []Response {

	// Get the puuid
	puuid, err := bot.riotapi.GetPuuid(riotid)
	if err != nil {
		fmt.Printf("Could not find a puuid for riot id %s\n", riotid)
		return NoResponseRiotApi(riotid)
	}

	// Get the rank of this player
	leagues, err := bot.riotapi.GetLeagues(puuid)
	if err != nil {
		fmt.Printf("Could not get rank for player %s\n", riotid)
		return NoResponseRiotApi(riotid)
	}

	// Send the final message
	fmt.Printf("Sending rank of player %s\n", riotid)
	return []Response{PlayerRank(riotid, leagues)}
}

func (bot *Bot) channel(discord *discordgo.Session, channelName string, guild *Guild) []Response {

	// Try to find the id from the channel name
	channelId, err := bot.getChannelId(discord, guild.id, channelName)
	if err != nil {
		fmt.Printf("Could not extract channel id from channel name %s\n", channelName)
		return ChannelDoesNotExist(channelName)
	}

	// We have a new channel to send messages to
	fmt.Printf("Changing channel used by guild %s to %s\n", guild.id, channelName)
	guild.channelId = channelId
	bot.database.SetChannel(guild.id, channelId)
	return ChannelChanged(channelName)
}

func (bot *Bot) status(discord *discordgo.Session, guild *Guild) []Response {

	// Very bad error if I cannot find the name of the channel to which
	// I am sending the messages
	// TODO: maybe finish this gracefully by updating the channel to the one
	// being used to send this message
	channelName, err := bot.getChannelName(discord, guild.id, guild.channelId)
	if err != nil {
		panic(fmt.Sprintf("Could not find channel name for channel id %s", guild.channelId))
	}

	// Create list of player names in this guild
	riotIds := []riotapi.RiotId{}
	for _, player := range bot.players {
		riotid, err := bot.riotapi.GetRiotId(player.id)
		if err != nil {
			panic(fmt.Sprintf("Could not find riot id for puuid %s in status message", player.id))
		}
		riotIds = append(riotIds, riotid)
	}
	return StatusMessage(riotIds, channelName)
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
			fmt.Printf("Could not find the riot id of the slected player %s\n", puuid)
			continue
		}
		// We have a player to check
		fmt.Printf("Checking in game status of player %s\n", riotid)
		spectator, err := bot.riotapi.GetSpectator(puuid)
		// At this point, a request has been performed in some form,
		// so the stopwatch needs to be reset
		player := bot.players[puuid]
		player.StopWatch.Start()
		if err != nil {
			fmt.Printf("Spectator data for player %s is not available\n", riotid)
			// Player is offline, update timeout if needed
			// TODO: could be an error of the riot api, and the player could be online
			if player.UpdateCheckTimeout(false, bot.offlineThreshold, bot.onlineTimeout, bot.offlineTimeout) {
				fmt.Printf("Player %s is now offline\n", riotid)
			}
			continue
		}
		// Player is online, update timeout if needed
		if player.UpdateCheckTimeout(true, bot.offlineThreshold, bot.onlineTimeout, bot.offlineTimeout) {
			fmt.Printf("Player %s is now online\n", &riotid)
		}
		// Get the guilds where this player is registered
		for _, guildid := range bot.getGuildIds(puuid) {
			guild := bot.guilds[guildid]
			if guild.lastInformedGameIds[puuid] == spectator.GameId {
				fmt.Printf("Spectator message for player %s in guild %s for this game (%d) was already sent\n", &riotid, guildid, spectator.GameId)
				continue
			}
			fmt.Printf("Spectator message for player %s in guild %s for this game (%d) has to be sent\n", &riotid, guildid, spectator.GameId)
			// Build the complete response
			responses := InGameMessage(puuid, riotid, spectator)
			bot.sendResponsesToGuild(responses, guildid)
			// Update last informed game id
			guild.lastInformedGameIds[puuid] = spectator.GameId
			bot.database.SetLastInformedGameId(puuid, guildid, spectator.GameId)
		}

	}

}

func (bot *Bot) selectPlayerToCheck() (riotapi.Puuid, bool) {

	fmt.Println("Selecting player to check in this iteration")
	var longestTimeStopped time.Duration
	var puuid riotapi.Puuid
	for _, player := range bot.players {
		riotid, err := bot.riotapi.GetRiotId(player.id)
		if err != nil {
			panic(fmt.Sprintf("Could not find riot id for puuid %s among my players", player.id))
		}
		// Time the stopwatch has been stopped for this player
		timeStopped := player.StopWatch.TimeStopped()
		if timeStopped > 0 {
			if timeStopped > longestTimeStopped {
				// This player is available to be checked,
				// and has been stopped more than the others,
				// so it's our best candidate
				fmt.Printf("%s: player has been stopped for longer\n", &riotid)
				longestTimeStopped = timeStopped
				puuid = player.id
			} else {
				// This player is available to check, but has been checked
				// more recently than others
				fmt.Printf("%s: player has been checked more recently than others\n", &riotid)
			}
		} else {
			fmt.Printf("Timeout still not reached for player %s\n", &riotid)
		}
	}
	// We have selected the best option to check
	if puuid == "" {
		fmt.Printf("Not checking any player during this iteration\n")
		return puuid, false
	} else {
		fmt.Printf("Checking player with puuid %s in this iteration\n", puuid)
		return puuid, true
	}
}

func (bot *Bot) getGuildIds(puuid riotapi.Puuid) []string {
	guildids := []string{}
	for _, guild := range bot.guilds {
		if _, ok := guild.lastInformedGameIds[puuid]; ok {
			guildids = append(guildids, guild.id)
			continue
		}
	}
	return guildids
}

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
	fmt.Println("Performing Riot API housekeeping")
	puuidsToKeep := make(map[riotapi.Puuid]struct{}, len(bot.players))
	for puuid := range bot.players {
		puuidsToKeep[puuid] = struct{}{}
	}
	bot.riotapi.Housekeeping(puuidsToKeep)
}
