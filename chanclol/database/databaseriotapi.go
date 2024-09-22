package database

import "chanclol/types"

type DatabaseRiotApi struct {
	Database
}

func CreatDatabaseRiotApi(filename string) DatabaseRiotApi {
	return DatabaseRiotApi{}
}

func (db *DatabaseRiotApi) GetChampions() map[types.ChampionId]string {
	return map[types.ChampionId]string{}
}

func (db *DatabaseRiotApi) SetChampions(champions map[types.ChampionId]string) {
}

func (db *DatabaseRiotApi) GetRiotIds() map[types.Puuid]types.RiotId {
	return map[types.Puuid]types.RiotId{}
}

func (db *DatabaseRiotApi) SetRiotId(puuid types.Puuid, riotid types.RiotId) {

}

func (db *DatabaseRiotApi) GetSummonerIds() map[types.Puuid]types.SummonerId {
	return map[types.Puuid]types.SummonerId{}
}

func (db *DatabaseRiotApi) SetSummonerId(puuid types.Puuid, summonerId types.SummonerId) {

}

func (db *DatabaseRiotApi) GetVersion() string {
	return ""
}
