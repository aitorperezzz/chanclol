package bot

import (
	"chanclol/internal/common"
	"chanclol/internal/riotapi"
	"time"
)

type Guild struct {
}

type Player struct {
	id         riotapi.Puuid
	StopWatch  common.Stopwatch
	lastOnline time.Time
}

type Bot struct {
	// client ?
	database                    DatabaseBot
	riotapi                     *riotapi.RiotApi
	guilds                      map[uint64]Guild
	players                     map[riotapi.Puuid]Player
	riotapiHousekeepingExecutor common.TimedExecutor
	offlineThreshold            time.Duration
	offlineTimeout              time.Duration
	onlineTimeout               time.Duration
	mainCycle                   time.Duration
}

func CreateBot(dbFilename string, riotapiHousekeepingTimeout time.Duration, offlineThreshold time.Duration, offlineTimeout time.Duration, onlineTimeout time.Duration, mainCycle time.Duration, riotapi *riotapi.RiotApi) Bot {

	var bot Bot

	// TODO: keep a copy of the client
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

	return bot

}

func (bot *Bot) riotapiHousekeeping() {
}
