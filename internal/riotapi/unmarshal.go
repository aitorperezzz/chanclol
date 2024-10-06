package riotapi

import (
	"encoding/json"
	"fmt"
	"strings"
	"sync"
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
			SummonerId SummonerId
			ChampionId ChampionId
			TeamId     int
		}
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return Spectator{}, err
	}

	// teams
	type ParticipantResult struct {
		Participant Participant
		TeamId      int
		Error       error
	}
	participantResults := make(chan ParticipantResult, len(raw.Participants))
	var wg sync.WaitGroup
	for _, rawPart := range raw.Participants {

		wg.Add(1)
		go func(ch chan<- ParticipantResult) {

			defer wg.Done()

			var err error

			// Extract data

			// riotid
			// Extract the riot id from participant data
			index := strings.Index(rawPart.RiotId, "#")
			if index == -1 {
				ch <- ParticipantResult{Error: fmt.Errorf("Riot id not correctly formatted inside participant data")}
				return
			}
			riotid := RiotId{GameName: rawPart.RiotId[:index], TagLine: rawPart.RiotId[index+1:]}

			// Request data

			// champion name
			var championName string
			if championName, err = riotapi.GetChampionName(rawPart.ChampionId); err != nil {
				ch <- ParticipantResult{Error: err}
				return
			}

			// champion mastery
			// TODO: I cannot distinguish if mastery is not available or
			// I have a problem connecting to riot API
			var mastery Mastery
			if mastery, err = riotapi.GetMastery(rawPart.Puuid, rawPart.ChampionId); err != nil {
				log.Debug().Msg(fmt.Sprintf("Mastery not available for puuid %s", string(rawPart.Puuid)))
			}

			// league
			var leagues []League
			if leagues, err = riotapi.GetLeaguesSummonerId(rawPart.SummonerId); err != nil {
				ch <- ParticipantResult{Error: err}
				return
			}

			participant := Participant{Puuid: rawPart.Puuid, Riotid: riotid, ChampionName: championName, Mastery: mastery, Leagues: leagues}

			// Return the participant to the channel
			ch <- ParticipantResult{Participant: participant, TeamId: rawPart.TeamId, Error: nil}

		}(participantResults)

	}
	wg.Wait()
	close(participantResults)

	// Gather all participants into a map of teams, and return early if an error was found
	teams := Teams{}
	for result := range participantResults {
		if result.Error != nil {
			return Spectator{}, result.Error
		}
		teams[result.TeamId] = append(teams[result.TeamId], result.Participant)
	}

	return Spectator{GameId: raw.GameId, GameMode: raw.GameMode, GameLength: time.Duration(raw.GameLength * int64(time.Second)), Teams: teams}, nil

}
