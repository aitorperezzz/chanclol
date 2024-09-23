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

func (db *DatabaseBot) GetGuilds() Guilds {
	return Guilds{}
}

func (db *DatabaseBot) AddGuild(guildid string, channelid string) {

}

func (db *DatabaseBot) AddPlayerToGuild(puuid riotapi.Puuid, guildid string) {

}

func (db *DatabaseBot) GetPlayers() Players {
	return Players{}
}
