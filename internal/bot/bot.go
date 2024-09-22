package bot

import (
	"chanclol/internal/common"
	"chanclol/internal/types"
)

type Guild struct {
}

type Player struct {
	League types.League
}

type BotConfig struct {
	dbFilename           string
	offlineThresholdMins int
	timeoutOnlineSecs    int
	timeoutOfflineSecs   int
	loopCycleSecs        int
}

type Bot struct {
	// client ?
	// database ?
	guilds              map[uint64]Guild
	players             map[uint64]Player
	riotapiHousekeeping common.TimedExecutor
}
