package bot

import (
	"path/filepath"
	"sync"
	"testing"
	"time"

	"chanclol/internal/riotapi"
)

func newTestBot(t *testing.T) Bot {
	t.Helper()

	return Bot{
		database:       NewDatabaseBot(filepath.Join(t.TempDir(), "bot.db")),
		mu:             &sync.RWMutex{},
		guilds:         Guilds{},
		players:        Players{},
		offlineTimeout: 30 * time.Second,
	}
}

func TestBotDataAddsGuildAndPersistsChannel(t *testing.T) {
	bot := newTestBot(t)

	if !bot.addGuildIfMissing("guild-1", "channel-1") {
		t.Fatal("expected guild to be added")
	}
	if bot.addGuildIfMissing("guild-1", "channel-ignored") {
		t.Fatal("expected existing guild not to be added again")
	}

	bot.setGuildChannel("guild-1", "channel-2")

	channelid, ok := bot.guildChannelId("guild-1")
	if !ok {
		t.Fatal("expected guild to exist")
	}
	if channelid != "channel-2" {
		t.Fatalf("expected channel-2, got %s", channelid)
	}

	guilds := bot.database.GetGuilds()
	if guilds["guild-1"].channelId != "channel-2" {
		t.Fatalf("expected persisted channel-2, got %s", guilds["guild-1"].channelId)
	}
}

func TestBotDataAddsAndRemovesPlayerAcrossGuilds(t *testing.T) {
	bot := newTestBot(t)
	puuid := riotapi.Puuid("puuid-1")

	bot.addGuildIfMissing("guild-1", "channel-1")
	bot.addGuildIfMissing("guild-2", "channel-2")

	if !bot.addPlayerToGuild(puuid, "guild-1") {
		t.Fatal("expected player to be added to guild-1")
	}
	if !bot.addPlayerToGuild(puuid, "guild-2") {
		t.Fatal("expected player to be added to guild-2")
	}
	if bot.addPlayerToGuild(puuid, "guild-1") {
		t.Fatal("expected duplicate player registration to be rejected")
	}

	removed, removedCompletely := bot.removePlayerFromGuild(puuid, "guild-1")
	if !removed || removedCompletely {
		t.Fatalf("expected player removed only from guild-1, got removed=%t removedCompletely=%t", removed, removedCompletely)
	}
	if _, ok := bot.players[puuid]; !ok {
		t.Fatal("expected player to remain globally registered")
	}

	removed, removedCompletely = bot.removePlayerFromGuild(puuid, "guild-2")
	if !removed || !removedCompletely {
		t.Fatalf("expected player removed completely, got removed=%t removedCompletely=%t", removed, removedCompletely)
	}
	if _, ok := bot.players[puuid]; ok {
		t.Fatal("expected player to be removed globally")
	}
}

func TestBotDataTracksRegisteredPuuidsAndLastInformedGame(t *testing.T) {
	bot := newTestBot(t)
	puuid := riotapi.Puuid("puuid-1")

	bot.addGuildIfMissing("guild-1", "channel-1")
	bot.addPlayerToGuild(puuid, "guild-1")

	registered := bot.registeredPuuids()
	if _, ok := registered[puuid]; !ok {
		t.Fatal("expected puuid to be registered")
	}

	if !bot.setLastInformedGameId(puuid, "guild-1", 123) {
		t.Fatal("expected last informed game id to be updated")
	}

	targets := bot.guildNotificationTargets(puuid, 456)
	if len(targets) != 1 {
		t.Fatalf("expected one notification target for a new game, got %d", len(targets))
	}
	targets = bot.guildNotificationTargets(puuid, 123)
	if len(targets) != 0 {
		t.Fatalf("expected no notification targets for an already informed game, got %d", len(targets))
	}

	guilds := bot.database.GetGuilds()
	if gameid := guilds["guild-1"].lastInformedGameIds[puuid]; gameid != 123 {
		t.Fatalf("expected persisted game id 123, got %d", gameid)
	}
}
