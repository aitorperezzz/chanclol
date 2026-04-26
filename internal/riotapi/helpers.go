package riotapi

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog/log"
)

// Raw participant received in the JSON from riot
type RawParticipant struct {
	Puuid      Puuid
	RiotId     string
	ChampionId ChampionId
	TeamId     int
}

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

// Build a spectator response from the JSON received from riot. This includes
// decoding the response and also making a few API calls
func BuildSpectator(data []byte, riotapi *RiotApi) (Spectator, error) {

	// unmarshall the full response
	var raw struct {
		GameId       GameId
		GameMode     string
		GameLength   int64
		Participants []RawParticipant
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return Spectator{}, err
	}

	// teams
	teams := Teams{}
	for _, rawParticipant := range raw.Participants {

		// Try to build the participant data, and print any error encountered.
		// The error is ignored through, because we still want to send a message even if
		// some participant data is missing or contains errors
		participant, err := BuildParticipantData(rawParticipant, riotapi)
		if err != nil {
			log.Error().Msg(fmt.Sprintf("Error building participant data for game id %d:", raw.GameId))
			log.Error().Msg(err.Error())
		}

		// In any case, add participant to the team
		teams[rawParticipant.TeamId] = append(teams[rawParticipant.TeamId], participant)
	}

	return Spectator{GameId: raw.GameId, GameMode: raw.GameMode, GameLength: time.Duration(raw.GameLength * int64(time.Second)), Teams: teams}, nil

}

func BuildParticipantData(raw RawParticipant, riotapi *RiotApi) (Participant, error) {

	var err error
	var participant Participant
	participant.Puuid = raw.Puuid

	// champion name
	var championName string
	if championName, err = riotapi.GetChampionName(raw.ChampionId); err != nil {
		return participant, err
	}
	participant.ChampionName = championName

	// riotid
	var riotid RiotId
	// Extract the riot id from participant data if correctly formatted
	// (this is not documented in the official API)
	index := strings.Index(raw.RiotId, "#")
	if index == -1 {
		log.Debug().Msg(fmt.Sprintf("Participant is anonymous or has no Riot ID available: %s", raw.RiotId))
		return participant, nil
	} else {
		riotid = RiotId{GameName: raw.RiotId[:index], TagLine: raw.RiotId[index+1:]}
	}
	participant.Riotid = riotid

	// at this point the riot id is valid and we can use it to retrieve the rest of the information

	// champion mastery
	// TODO: I cannot distinguish if mastery is not available or
	// I have a problem connecting to riot API
	var mastery Mastery
	if mastery, err = riotapi.GetMastery(raw.Puuid, raw.ChampionId); err != nil {
		log.Debug().Msg(fmt.Sprintf("Mastery not available for puuid %s", string(raw.Puuid)))
	}
	participant.Mastery = mastery

	// leagues
	var leagues []League
	if leagues, err = riotapi.GetLeagues(raw.Puuid); err != nil {
		return participant, err
	}
	participant.Leagues = leagues

	return participant, nil

}
