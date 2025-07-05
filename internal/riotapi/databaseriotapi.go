package riotapi

import "chanclol/internal/common"

type DatabaseRiotApi struct {
	common.Database
}

func CreatDatabaseRiotApi(filename string) DatabaseRiotApi {
	return DatabaseRiotApi{}
}

func (db *DatabaseRiotApi) GetChampions() map[ChampionId]string {
	return map[ChampionId]string{}
}

func (db *DatabaseRiotApi) SetChampions(champions map[ChampionId]string) {
}

func (db *DatabaseRiotApi) GetRiotIds() map[Puuid]RiotId {
	return map[Puuid]RiotId{}
}

func (db *DatabaseRiotApi) SetRiotIds(riotids map[Puuid]RiotId) {

}

func (db *DatabaseRiotApi) SetRiotId(puuid Puuid, riotid RiotId) {

}

func (db *DatabaseRiotApi) GetVersion() string {
	return ""
}

func (db *DatabaseRiotApi) SetVersion(version string) {

}
