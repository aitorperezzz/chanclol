package riotapi

import (
	"chanclol/types"
	"encoding/json"
	"time"
)

func DecodeRiotId(data []byte) (types.RiotId, error) {

	// unmarshal
	var riotid types.RiotId
	if err := json.Unmarshal(data, &riotid); err != nil {
		return types.RiotId{}, err
	}
	return riotid, nil
}

func DecodePuuid(data []byte) (types.Puuid, error) {

	var puuid struct {
		Puuid string
	}
	if err := json.Unmarshal(data, &puuid); err != nil {
		return "", err
	}

	return types.Puuid(puuid.Puuid), nil
}

func DecodeLeagues(data []byte) ([]types.League, error) {

	// unmarshal
	var leagues []types.League
	if err := json.Unmarshal(data, &leagues); err != nil {
		return nil, err
	}

	// Handle internal data
	for _, league := range leagues {

		// winrate
		games := float32(league.Wins) + float32(league.Losses)
		if games > 0 {
			league.Winrate = (100.0 * float32(league.Wins) / games)
		} else {
			league.Winrate = 0
		}
	}

	return leagues, nil
}

func DecodeMastery(data []byte) (types.Mastery, error) {

	// unmarshal
	var raw struct {
		ChampionLevel int
		LastPlayTime  int64
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return types.Mastery{}, err
	}

	return types.Mastery{Level: raw.ChampionLevel, LastPlayed: time.Unix(0, raw.LastPlayTime*int64(time.Millisecond))}, nil
}

func DecodeGameId(data []byte) (types.GameId, error) {

	var gameId struct{ GameId types.GameId }
	if err := json.Unmarshal(data, &gameId); err != nil {
		return 0, err
	}
	return gameId.GameId, nil
}

func DecodeSpectator(data []byte, riotapi *RiotApi) (types.Spectator, error) {

	// unmarshal
	var raw struct {
		GameId       types.GameId
		GameMode     string
		GameLength   int64
		Participants []struct {
			puuid      types.Puuid
			championId types.ChampionId
			teamId     int
		}
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return types.Spectator{}, err
	}

	// teams
	teams := types.Teams{}
	for _, part := range raw.Participants {

		var err error

		// Request all the necessary data for this participant

		// riotid
		var riotid types.RiotId
		if riotid, err = riotapi.GetRiotId(part.puuid); err != nil {
			return types.Spectator{}, err
		}

		// champion name
		var championName string
		if championName, err = riotapi.GetChampionName(part.championId); err != nil {
			return types.Spectator{}, err
		}

		// champion mastery
		var mastery types.Mastery
		if mastery, err = riotapi.GetMastery(part.puuid, part.championId); err != nil {
			return types.Spectator{}, err
		}

		// league
		var leagues []types.League
		if leagues, err = riotapi.GetLeagues(part.puuid); err != nil {
			return types.Spectator{}, err
		}

		participant := types.Participant{Puuid: part.puuid, Riotid: riotid, ChampionName: championName, Mastery: mastery, Leagues: leagues}

		// Add participant to the team
		teams[part.teamId] = append(teams[part.teamId], participant)
	}

	return types.Spectator{GameId: raw.GameId, GameMode: raw.GameMode, GameLength: time.Duration(raw.GameLength * int64(time.Second)), Teams: teams}, nil

}
