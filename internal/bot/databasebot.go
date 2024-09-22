package bot

import (
	"chanclol/internal/common"
	"chanclol/internal/riotapi"
)

type DatabaseBot struct {
	common.Database
}

func CreateDatabaseBot(dbFilename string) DatabaseBot {
	return DatabaseBot{}
}

func (db *DatabaseBot) GetGuilds() map[uint64]Guild {
	return map[uint64]Guild{}
}

func (db *DatabaseBot) GetPlayers() map[riotapi.Puuid]Player {
	return map[riotapi.Puuid]Player{}
}
