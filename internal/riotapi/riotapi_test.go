package riotapi

import (
	"chanclol/internal/common"
	"errors"
	"path/filepath"
	"testing"
)

func TestGetPuuidReturnsNotFoundOn404(t *testing.T) {
	riotapi := NewRiotApi(filepath.Join(t.TempDir(), "riotapi.db"), "api-key", nil)
	riotapi.requestDataFn = func(url string, vital bool) ([]byte, error) {
		return nil, common.ErrNotFound
	}

	_, err := riotapi.GetPuuid(RiotId{GameName: "Missing", TagLine: "EUW"})
	if !errors.Is(err, common.ErrNotFound) {
		t.Fatalf("expected ErrNotFound, got %v", err)
	}
}

func TestGetLeaguesReturnsNotFoundOn404(t *testing.T) {
	riotapi := NewRiotApi(filepath.Join(t.TempDir(), "riotapi.db"), "api-key", nil)
	riotapi.requestDataFn = func(url string, vital bool) ([]byte, error) {
		return nil, common.ErrNotFound
	}

	leagues, err := riotapi.GetLeagues("missing-puuid")
	if !errors.Is(err, common.ErrNotFound) {
		t.Fatalf("expected ErrNotFound, got %v", err)
	}
	if leagues != nil {
		t.Fatalf("expected nil leagues on error, got %v", leagues)
	}
}

func TestReplaceSpectatorForPlayerRemovesStaleGames(t *testing.T) {
	riotapi := NewRiotApi(filepath.Join(t.TempDir(), "riotapi.db"), "api-key", nil)
	puuid := Puuid("puuid-1")

	riotapi.replaceSpectatorForPlayer(puuid, 1, Spectator{
		GameId: 1,
		Teams: Teams{
			100: Team{{Puuid: puuid}},
		},
	})

	removed := riotapi.replaceSpectatorForPlayer(puuid, 2, Spectator{
		GameId: 2,
		Teams: Teams{
			100: Team{{Puuid: puuid}},
		},
	})

	if removed != 1 {
		t.Fatalf("expected one stale game to be removed, got %d", removed)
	}
	gameIds := riotapi.GetGameIds(puuid)
	if len(gameIds) != 1 {
		t.Fatalf("expected one cached game for player, got %d", len(gameIds))
	}
	if _, ok := gameIds[2]; !ok {
		t.Fatalf("expected game 2 to remain cached, got %v", gameIds)
	}
}
