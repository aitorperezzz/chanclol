package riotapi

import (
	"path/filepath"
	"testing"
)

func TestBuildParticipantDataSkipsAnonymousParticipantDetails(t *testing.T) {
	dbFilename := filepath.Join(t.TempDir(), "riotapi.db")
	riotapi := NewRiotApi(dbFilename, "api-key", nil)
	riotapi.champions[142] = "Zoe"

	participant, err := BuildParticipantData(RawParticipant{
		RiotId:     "Zoe",
		ChampionId: 142,
		TeamId:     100,
	}, &riotapi)
	if err != nil {
		t.Fatalf("expected anonymous participant not to fail, got %v", err)
	}
	if participant.ChampionName != "Zoe" {
		t.Fatalf("expected champion name Zoe, got %s", participant.ChampionName)
	}
	if participant.Riotid != (RiotId{}) {
		t.Fatalf("expected empty Riot ID, got %s", participant.Riotid)
	}
	if participant.Mastery.Available {
		t.Fatal("expected mastery to be skipped")
	}
	if len(participant.Leagues) != 0 {
		t.Fatalf("expected leagues to be skipped, got %d", len(participant.Leagues))
	}
}
