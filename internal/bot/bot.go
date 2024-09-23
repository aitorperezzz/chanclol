package bot

import (
	"chanclol/internal/common"
	"chanclol/internal/riotapi"
	"fmt"
	"os"
	"os/signal"
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

type Guilds map[string]Guild
type Players map[riotapi.Puuid]Player

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
	discord, err := discordgo.New("Bot " + bot.token)
	if err != nil {
		return fmt.Errorf("could not create discord session")
	}

	// Event handler
	discord.AddHandler(bot.Receive)

	// Open session
	discord.Open()
	defer discord.Close()

	// keep bot running untill there is NO os interruption (ctrl + C)
	fmt.Println("Starting infinite loop")
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt)
	<-c

	return nil
}

func (bot *Bot) Receive(discord *discordgo.Session, message *discordgo.MessageCreate) {

	// Reject my own messages
	if message.Author.ID == discord.State.User.ID {
		fmt.Printf("Rejecting my own message")
		return
	}

	// Ignore messages from private channels
	if message.GuildID == "" {
		fmt.Println("Ignoring private message")
		content := "For the time being, I am ignoring private messages"
		bot.sendResponses(discord, message.ChannelID, []Response{{content: content}})
		return
	}

	// Register the guild if it's the first time I see it
	if _, ok := bot.guilds[message.GuildID]; !ok {
		fmt.Printf("Initialising guild %s", message.GuildID)
		bot.guilds[message.GuildID] = Guild{id: message.GuildID, channelId: message.ChannelID}
		bot.database.AddGuild(message.GuildID, message.ChannelID)
		fmt.Println("Sending welcome message")

		// extract the name of the channel
		channelName, err := bot.getChannelName(discord, message.GuildID, message.ChannelID)
		if err != nil {
			fmt.Printf("Could not extract channel name for channel id %s", message.ChannelID)
			return
		}

		// Send welcome message
		bot.sendResponses(discord, message.ChannelID, Welcome(channelName))
	}
	guild := bot.guilds[message.GuildID]

	// Parse the input provided and call the appropriate function
	fmt.Printf("Received message: %s", message.Content)
	parseResult := Parse(message.Content)
	switch parseResult.parseid {
	case PARSEID_NO_BOT_PREFIX:
		fmt.Printf("Rejecting message not intended for the bot")
		return
	case PARSEID_OK:
		fmt.Printf("Command understood: %s", message.Content)
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
		bot.sendResponses(discord, message.ChannelID, responses)
	default:

		// The command is invalid input, so it contains an error message
		errorMessage := parseResult.errorMessage
		fmt.Printf("Wrong input: '%s'. Reason: %s ", message.Content, errorMessage)
		bot.sendResponses(discord, message.ChannelID, InputNotValid(errorMessage))
	}
}

func (bot *Bot) sendResponses(discord *discordgo.Session, channelId string, responses []Response) {
	for _, response := range responses {
		// TODO: send the embed as well
		discord.ChannelMessageSend(channelId, response.content)
	}
}

func (bot *Bot) register(riotid riotapi.RiotId, guild Guild) []Response {

	// Get the puuid
	puuid, err := bot.riotapi.GetPuuid(riotid)
	if err != nil {
		fmt.Printf("Puuid not found for riot id %s", &riotid)
		return NoResponseRiotApi(riotid)
	}

	// Check if player already belongs to the guild
	if _, ok := guild.lastInformedGameIds[puuid]; ok {
		fmt.Printf("Player %s is already registered in guild %s", riotid, guild.id)
		return PlayerAlreadyRegistered(riotid)
	}

	// Get rank of this player
	leagues, err := bot.riotapi.GetLeagues(puuid)
	if err != nil {
		fmt.Printf("Could not get rank from Riot API for player %s", &riotid)
	}

	// Now it's safe to register the player
	fmt.Printf("Registering player %s in guild %s", &riotid, guild.id)
	// Add it to my complete list of players if necessary
	if _, ok := bot.players[puuid]; !ok {
		player := Player{id: puuid}
		player.StopWatch.Timeout = bot.offlineTimeout
		bot.players[puuid] = player
	}
	// Add to the guild
	guild.lastInformedGameIds[puuid] = 0
	// Add to the database
	bot.database.AddPlayerToGuild(puuid, guild.id)

	// Send the final message
	fmt.Printf("Player %s has been registered in guild %s", &riotid, guild.id)
	return []Response{
		PlayerRegistered(riotid),
		PlayerRank(riotid, leagues),
	}
}

func (bot *Bot) unregister(riotid riotapi.RiotId, guild Guild) []Response {

	// Get the puuid
	puuid, err := bot.riotapi.GetPuuid(riotid)
	if err != nil {
		fmt.Printf("Could not find a puuid for riot id %s", riotid)
		return NoResponseRiotApi(riotid)
	}

	// Check if the player was registered in the guild
	if _, ok := guild.lastInformedGameIds[puuid]; !ok {
		fmt.Printf("Player %s was not previously registered in guild %s", riotid, guild.id)
		return PlayerNotPreviouslyRegistered(riotid)
	}

	// Check if the player was registered in the guild
	fmt.Printf("Unregistering player %s from guild id %s", riotid, guild.id)
	delete(guild.lastInformedGameIds, puuid)
	// Remove from the database
	bot.database.RemovePlayerFromGuild(puuid, guild.id)
	fmt.Printf("Player %s has been unregistered from guild %s", riotid, guild.id)
	// If the player does not belong to ANY guild, remove it completely
	if len(bot.getGuildIds(puuid)) == 0 {
		delete(bot.players, puuid)
		fmt.Printf("Player %s removed completely", riotid)
	}
	return PlayerUnregistered(riotid)
}

func (bot *Bot) rank(riotid riotapi.RiotId) []Response {

	// Get the puuid
	puuid, err := bot.riotapi.GetPuuid(riotid)
	if err != nil {
		fmt.Printf("Could not find a puuid for riot id %s", riotid)
		return NoResponseRiotApi(riotid)
	}

	// Get the rank of this player
	leagues, err := bot.riotapi.GetLeagues(puuid)
	if err != nil {
		fmt.Printf("Could not get rank for player %s", riotid)
		return NoResponseRiotApi(riotid)
	}

	// Send the final message
	fmt.Printf("Sending rank of player %s", riotid)
	return []Response{PlayerRank(riotid, leagues)}
}

func (bot *Bot) channel(discord *discordgo.Session, channelName string, guild Guild) []Response {

	// Try to find the id from the channel name
	channelId, err := bot.getChannelId(discord, guild.id, channelName)
	if err != nil {
		fmt.Printf("Could not extract channel id from channel name %s", channelName)
		return ChannelDoesNotExist(channelName)
	}

	// We have a new channel to send messages to
	fmt.Printf("Changing channel used by guild %s to %s", guild.id, channelName)
	guild.channelId = channelId
	bot.database.SetChannel(guild.id, channelId)
	return ChannelChanged(channelName)
}

func (bot *Bot) status(discord *discordgo.Session, guild Guild) []Response {

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
}
