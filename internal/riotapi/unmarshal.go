package riotapi

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/rs/zerolog/log"
)

func UnmarshalPuuid(data []byte) (Puuid, error) {

	var puuid struct {
		Puuid string
	}
	if err := json.Unmarshal(data, &puuid); err != nil {
		return "", err
	}

	return Puuid(puuid.Puuid), nil
}

func UnmarshalLeagues(data []byte) ([]League, error) {

	// unmarshal
	var leagues []League
	if err := json.Unmarshal(data, &leagues); err != nil {
		return nil, err
	}

	// Handle internal data
	for i := range leagues {

		// winrate
		games := leagues[i].Wins + leagues[i].Losses
		if games > 0 {
			leagues[i].Winrate = 100.0 * float32(leagues[i].Wins) / float32(games)
		} else {
			leagues[i].Winrate = 0
		}
	}

	return leagues, nil
}

func UnmarshalMastery(data []byte) (Mastery, error) {

	// unmarshal
	var raw struct {
		ChampionLevel int
		LastPlayTime  int64
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return Mastery{}, err
	}

	return Mastery{Level: raw.ChampionLevel, LastPlayed: time.Unix(0, raw.LastPlayTime*int64(time.Millisecond)), Available: true}, nil
}

func UnmarshalGameId(data []byte) (GameId, error) {

	var gameId struct{ GameId GameId }
	if err := json.Unmarshal(data, &gameId); err != nil {
		return 0, err
	}
	return gameId.GameId, nil
}

func UnmarshalSpectator(data []byte, riotapi *RiotApi) (Spectator, error) {

	// unmarshal
	var raw struct {
		GameId       GameId
		GameMode     string
		GameLength   int64
		Participants []struct {
			Puuid      Puuid
			ChampionId ChampionId
			TeamId     int
		}
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return Spectator{}, err
	}

	// teams
	teams := Teams{}
	for _, part := range raw.Participants {

		var err error

		// Request all the necessary data for this participant

		// riotid
		// TODO: the riot id is already present in the participant data
		var riotid RiotId
		if riotid, err = riotapi.GetRiotId(part.Puuid); err != nil {
			return Spectator{}, err
		}

		// champion name
		var championName string
		if championName, err = riotapi.GetChampionName(part.ChampionId); err != nil {
			return Spectator{}, err
		}

		// champion mastery
		// TODO: I cannot distinguish if mastery is not available or
		// I have a problem connecting to riot API
		var mastery Mastery
		if mastery, err = riotapi.GetMastery(part.Puuid, part.ChampionId); err != nil {
			log.Debug().Msg(fmt.Sprintf("Mastery not available for puuid %s", string(part.Puuid)))
		}

		// league
		var leagues []League
		if leagues, err = riotapi.GetLeagues(part.Puuid); err != nil {
			return Spectator{}, err
		}

		participant := Participant{Puuid: part.Puuid, Riotid: riotid, ChampionName: championName, Mastery: mastery, Leagues: leagues}

		// Add participant to the team
		teams[part.TeamId] = append(teams[part.TeamId], participant)
	}

	return Spectator{GameId: raw.GameId, GameMode: raw.GameMode, GameLength: time.Duration(raw.GameLength * int64(time.Second)), Teams: teams}, nil

}
