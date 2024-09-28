package riotapi

import (
	"fmt"
	"time"
)

type Puuid string
type SummonerId string
type ChampionId int
type GameId int64
type Team []Participant
type Teams map[int]Team

type RiotId struct {
	GameName string
	TagLine  string
}

type Mastery struct {
	Level      int
	LastPlayed time.Time
	Available  bool
}

type League struct {
	QueueType string
	Tier      string
	Rank      string
	Lps       int
	Wins      int
	Losses    int
	Winrate   float32
}

type Spectator struct {
	GameId     GameId
	GameMode   string
	GameLength time.Duration
	Teams      Teams
}

type Participant struct {
	Puuid        Puuid
	Riotid       RiotId
	ChampionName string
	Mastery      Mastery
	Leagues      []League
}

func (riotid *RiotId) String() string {
	return fmt.Sprintf("%s#%s", riotid.GameName, riotid.TagLine)
}
