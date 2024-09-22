package bot

import (
	"chanclol/internal/common"
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

func (db *DatabaseBot) GetPlayers() Players {
	return Players{}
}

func (db *DatabaseBot) AddGuild(guildid string, channelid string) {

}
