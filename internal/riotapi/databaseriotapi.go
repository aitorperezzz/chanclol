package riotapi

import (
	"chanclol/internal/common"

	"github.com/rs/zerolog/log"
)

type DatabaseRiotApi struct {
	common.Database
	data databaseRiotApiData
}

type databaseRiotApiData struct {
	Champions map[ChampionId]string `json:"champions"`
	RiotIds   map[Puuid]RiotId      `json:"riot_ids"`
	Version   string                `json:"version"`
}

func CreateDatabaseRiotApi(filename string) DatabaseRiotApi {
	db := DatabaseRiotApi{
		Database: common.NewDatabase(filename),
		data: databaseRiotApiData{
			Champions: map[ChampionId]string{},
			RiotIds:   map[Puuid]RiotId{},
		},
	}
	if err := db.Load(&db.data); err != nil {
		log.Error().Err(err).Msg("Could not load Riot API database")
	}
	if db.data.Champions == nil {
		db.data.Champions = map[ChampionId]string{}
	}
	if db.data.RiotIds == nil {
		db.data.RiotIds = map[Puuid]RiotId{}
	}
	return db
}

func (db *DatabaseRiotApi) GetChampions() map[ChampionId]string {
	champions := make(map[ChampionId]string, len(db.data.Champions))
	for championId, name := range db.data.Champions {
		champions[championId] = name
	}
	return champions
}

func (db *DatabaseRiotApi) SetChampions(champions map[ChampionId]string) {
	db.data.Champions = make(map[ChampionId]string, len(champions))
	for championId, name := range champions {
		db.data.Champions[championId] = name
	}
	db.save()
}

func (db *DatabaseRiotApi) GetRiotIds() map[Puuid]RiotId {
	riotids := make(map[Puuid]RiotId, len(db.data.RiotIds))
	for puuid, riotid := range db.data.RiotIds {
		riotids[puuid] = riotid
	}
	return riotids
}

func (db *DatabaseRiotApi) SetRiotIds(riotids map[Puuid]RiotId) {
	db.data.RiotIds = make(map[Puuid]RiotId, len(riotids))
	for puuid, riotid := range riotids {
		db.data.RiotIds[puuid] = riotid
	}
	db.save()
}

func (db *DatabaseRiotApi) SetRiotId(puuid Puuid, riotid RiotId) {
	db.data.RiotIds[puuid] = riotid
	db.save()
}

func (db *DatabaseRiotApi) GetVersion() string {
	return db.data.Version
}

func (db *DatabaseRiotApi) SetVersion(version string) {
	db.data.Version = version
	db.save()
}

func (db *DatabaseRiotApi) save() {
	if err := db.Save(&db.data); err != nil {
		log.Error().Err(err).Msg("Could not save Riot API database")
	}
}
