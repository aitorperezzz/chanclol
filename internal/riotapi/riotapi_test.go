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
