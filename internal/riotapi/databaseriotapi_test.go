package riotapi

import (
	"path/filepath"
	"testing"
)

func TestDatabaseRiotApiPersistsCachedData(t *testing.T) {
	filename := filepath.Join(t.TempDir(), "riotapi.db")

	db := CreateDatabaseRiotApi(filename)
	db.SetChampions(map[ChampionId]string{1: "Annie"})
	db.SetRiotId("puuid-1", RiotId{GameName: "Player", TagLine: "EUW"})
	db.SetVersion("16.8.1")

	reloaded := CreateDatabaseRiotApi(filename)
	if champion := reloaded.GetChampions()[1]; champion != "Annie" {
		t.Fatalf("expected champion Annie, got %s", champion)
	}
	if riotid := reloaded.GetRiotIds()["puuid-1"]; riotid.String() != "Player#EUW" {
		t.Fatalf("expected Player#EUW, got %s", riotid.String())
	}
	if version := reloaded.GetVersion(); version != "16.8.1" {
		t.Fatalf("expected version 16.8.1, got %s", version)
	}
}
