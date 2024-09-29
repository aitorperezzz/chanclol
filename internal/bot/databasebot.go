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
	return make(Guilds)
}

func (db *DatabaseBot) AddGuild(guildid string, channelid string) {

}

func (db *DatabaseBot) SetChannel(guildid string, channelid string) {

}

func (db *DatabaseBot) AddPlayerToGuild(puuid riotapi.Puuid, guildid string) {

}

func (db *DatabaseBot) RemovePlayerFromGuild(puuid riotapi.Puuid, guildid string) {

}

func (db *DatabaseBot) SetLastInformedGameId(puuid riotapi.Puuid, guildid string, gameid riotapi.GameId) {

}

func (db *DatabaseBot) GetPlayers() Players {
	return make(Players)
}
