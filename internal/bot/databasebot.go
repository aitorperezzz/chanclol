package bot

import (
	"chanclol/internal/common"
	"chanclol/internal/riotapi"

	"github.com/rs/zerolog/log"
)

type DatabaseBot struct {
	common.Database
	data databaseBotData
}

type databaseBotData struct {
	Guilds map[string]databaseGuild `json:"guilds"`
}

type databaseGuild struct {
	ChannelId           string                           `json:"channel_id"`
	LastInformedGameIds map[riotapi.Puuid]riotapi.GameId `json:"last_informed_game_ids"`
}

func NewDatabaseBot(dbFilename string) DatabaseBot {
	db := DatabaseBot{
		Database: common.NewDatabase(dbFilename),
		data:     databaseBotData{Guilds: map[string]databaseGuild{}},
	}
	if err := db.Load(&db.data); err != nil {
		log.Error().Err(err).Msg("Could not load bot database")
	}
	if db.data.Guilds == nil {
		db.data.Guilds = map[string]databaseGuild{}
	}
	return db
}

func (db *DatabaseBot) GetGuilds() Guilds {
	guilds := make(Guilds, len(db.data.Guilds))
	for guildId, storedGuild := range db.data.Guilds {
		lastInformedGameIds := make(map[riotapi.Puuid]riotapi.GameId, len(storedGuild.LastInformedGameIds))
		for puuid, gameId := range storedGuild.LastInformedGameIds {
			lastInformedGameIds[puuid] = gameId
		}
		guilds[guildId] = &Guild{
			id:                  guildId,
			channelId:           storedGuild.ChannelId,
			lastInformedGameIds: lastInformedGameIds,
		}
	}
	return guilds
}

func (db *DatabaseBot) AddGuild(guildid string, channelid string) {
	if _, ok := db.data.Guilds[guildid]; !ok {
		db.data.Guilds[guildid] = databaseGuild{
			ChannelId:           channelid,
			LastInformedGameIds: map[riotapi.Puuid]riotapi.GameId{},
		}
	} else {
		storedGuild := db.data.Guilds[guildid]
		storedGuild.ChannelId = channelid
		db.data.Guilds[guildid] = storedGuild
	}
	db.save()
}

func (db *DatabaseBot) SetChannel(guildid string, channelid string) {
	storedGuild := db.ensureGuild(guildid)
	storedGuild.ChannelId = channelid
	db.data.Guilds[guildid] = storedGuild
	db.save()
}

func (db *DatabaseBot) AddPlayerToGuild(puuid riotapi.Puuid, guildid string) {
	storedGuild := db.ensureGuild(guildid)
	storedGuild.LastInformedGameIds[puuid] = 0
	db.data.Guilds[guildid] = storedGuild
	db.save()
}

func (db *DatabaseBot) RemovePlayerFromGuild(puuid riotapi.Puuid, guildid string) {
	storedGuild := db.ensureGuild(guildid)
	delete(storedGuild.LastInformedGameIds, puuid)
	db.data.Guilds[guildid] = storedGuild
	db.save()
}

func (db *DatabaseBot) SetLastInformedGameId(puuid riotapi.Puuid, guildid string, gameid riotapi.GameId) {
	storedGuild := db.ensureGuild(guildid)
	storedGuild.LastInformedGameIds[puuid] = gameid
	db.data.Guilds[guildid] = storedGuild
	db.save()
}

func (db *DatabaseBot) GetPlayers() Players {
	players := make(Players)
	for _, guild := range db.data.Guilds {
		for puuid := range guild.LastInformedGameIds {
			players[puuid] = &Player{id: puuid}
		}
	}
	return players
}

func (db *DatabaseBot) ensureGuild(guildid string) databaseGuild {
	storedGuild, ok := db.data.Guilds[guildid]
	if !ok {
		storedGuild = databaseGuild{
			LastInformedGameIds: map[riotapi.Puuid]riotapi.GameId{},
		}
	}
	if storedGuild.LastInformedGameIds == nil {
		storedGuild.LastInformedGameIds = map[riotapi.Puuid]riotapi.GameId{}
	}
	return storedGuild
}

func (db *DatabaseBot) save() {
	if err := db.Save(&db.data); err != nil {
		log.Error().Err(err).Msg("Could not save bot database")
	}
}
