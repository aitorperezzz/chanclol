package riotapi

import (
	"encoding/json"
	"fmt"
	"strings"
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
			RiotId     string
			ChampionId ChampionId
			TeamId     int
		}
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return Spectator{}, err
	}

	// teams
	teams := Teams{}
	for _, rawParticipant := range raw.Participants {

		var err error

		// Request all the necessary data for this participant

		// riotid
		var riotid RiotId
		// Extract the riot id from participant data if correctly formatted
		// (this is not documented in the official API)
		index := strings.Index(rawParticipant.RiotId, "#")
		if index == -1 {
			log.Error().Msg(fmt.Sprintf("Riot id '%s' is not correctly formatted inside participant data", rawParticipant.RiotId))
			// Try retrieving it through a normal API call
			if riotid, err = riotapi.GetRiotId(rawParticipant.Puuid); err != nil {
				return Spectator{}, err
			}
		} else {
			riotid = RiotId{GameName: rawParticipant.RiotId[:index], TagLine: rawParticipant.RiotId[index+1:]}
		}

		// champion name
		var championName string
		if championName, err = riotapi.GetChampionName(rawParticipant.ChampionId); err != nil {
			return Spectator{}, err
		}

		// champion mastery
		// TODO: I cannot distinguish if mastery is not available or
		// I have a problem connecting to riot API
		var mastery Mastery
		if mastery, err = riotapi.GetMastery(rawParticipant.Puuid, rawParticipant.ChampionId); err != nil {
			log.Debug().Msg(fmt.Sprintf("Mastery not available for puuid %s", string(rawParticipant.Puuid)))
		}

		// league
		var leagues []League
		if leagues, err = riotapi.GetLeagues(rawParticipant.Puuid); err != nil {
			return Spectator{}, err
		}

		participant := Participant{Puuid: rawParticipant.Puuid, Riotid: riotid, ChampionName: championName, Mastery: mastery, Leagues: leagues}

		// Add participant to the team
		teams[rawParticipant.TeamId] = append(teams[rawParticipant.TeamId], participant)
	}

	return Spectator{GameId: raw.GameId, GameMode: raw.GameMode, GameLength: time.Duration(raw.GameLength * int64(time.Second)), Teams: teams}, nil

}
