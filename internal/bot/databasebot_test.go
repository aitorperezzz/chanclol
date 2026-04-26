package bot

import (
	"path/filepath"
	"testing"

	"chanclol/internal/riotapi"
)

func TestDatabaseBotPersistsGuildsAndPlayers(t *testing.T) {
	filename := filepath.Join(t.TempDir(), "bot.db")

	db := NewDatabaseBot(filename)
	db.AddGuild("guild-1", "channel-1")
	db.AddPlayerToGuild("puuid-1", "guild-1")
	db.SetLastInformedGameId("puuid-1", "guild-1", 123)
	db.SetChannel("guild-1", "channel-2")

	reloaded := NewDatabaseBot(filename)
	guilds := reloaded.GetGuilds()
	guild, ok := guilds["guild-1"]
	if !ok {
		t.Fatal("expected guild to be restored")
	}
	if guild.channelId != "channel-2" {
		t.Fatalf("expected channel-2, got %s", guild.channelId)
	}
	if gameId := guild.lastInformedGameIds[riotapi.Puuid("puuid-1")]; gameId != 123 {
		t.Fatalf("expected game id 123, got %d", gameId)
	}

	players := reloaded.GetPlayers()
	if _, ok := players[riotapi.Puuid("puuid-1")]; !ok {
		t.Fatal("expected player to be restored")
	}
}
