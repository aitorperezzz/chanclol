package bot

import (
	"chanclol/internal/common"
	"chanclol/internal/riotapi"
	"testing"
)

func TestRiotAccountErrorFormatsNotFound(t *testing.T) {
	riotid := riotapi.RiotId{GameName: "Player", TagLine: "EUW"}
	responses := RiotAccountError(riotid, common.ErrNotFound)

	response, ok := responses[0].(ResponseString)
	if !ok {
		t.Fatalf("expected ResponseString, got %T", responses[0])
	}
	if response.string != "Player `Player#EUW` does not exist" {
		t.Fatalf("unexpected response: %s", response.string)
	}
}

func TestRiotApiErrorFormatsTemporaryError(t *testing.T) {
	riotid := riotapi.RiotId{GameName: "Player", TagLine: "EUW"}
	responses := RiotApiError(riotid, common.ErrRateLimited)

	response, ok := responses[0].(ResponseString)
	if !ok {
		t.Fatalf("expected ResponseString, got %T", responses[0])
	}
	if response.string != "I could not check player `Player#EUW` right now. Please try again in a bit" {
		t.Fatalf("unexpected response: %s", response.string)
	}
}

func TestPlayerRankFormatsEmptyLeaguesAsUnranked(t *testing.T) {
	riotid := riotapi.RiotId{GameName: "Player", TagLine: "EUW"}
	response := PlayerRank(riotid, nil)

	responseString, ok := response.(ResponseString)
	if !ok {
		t.Fatalf("expected ResponseString, got %T", response)
	}
	if responseString.string != "Player `Player#EUW` is not ranked" {
		t.Fatalf("unexpected response: %s", responseString.string)
	}
}
