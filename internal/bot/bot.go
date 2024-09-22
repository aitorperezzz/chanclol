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
		channels, err := discord.GuildChannels(message.GuildID)
		if err != nil {
			fmt.Printf("Could not extract list of channels of guild id %s", message.GuildID)
			return
		}
		var channel *discordgo.Channel
		for _, ch := range channels {
			if ch.ID == message.ChannelID {
				channel = ch
				break
			}
		}
		if channel.Name == "" {
			fmt.Printf("Could not extract channel name for channel id %s in guild id %s", channel.ID, message.GuildID)
			return
		}

		// Send welcome message
		bot.sendResponses(discord, message.ChannelID, Welcome(channel.Name))
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
				responses = bot.channel(channelName, guild)
			}
		case COMMAND_STATUS:
			responses = bot.status(guild)
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
	return []Response{}
}

func (bot *Bot) unregister(riotid riotapi.RiotId, guild Guild) []Response {
	return []Response{}
}

func (bot *Bot) rank(riotid riotapi.RiotId) []Response {
	return []Response{}
}

func (bot *Bot) channel(channelName string, guild Guild) []Response {
	return []Response{}
}

func (bot *Bot) status(guild Guild) []Response {
	return []Response{}
}

func (bot *Bot) riotapiHousekeeping() {
}
