package bot

import (
	"chanclol/internal/riotapi"
	"time"
)

type playerCheckState struct {
	puuid   riotapi.Puuid
	stopped bool
	elapsed time.Duration
}

type guildNotificationTarget struct {
	guildid   string
	channelid string
}

func (bot *Bot) addGuildIfMissing(guildid string, channelid string) bool {
	bot.mu.Lock()
	defer bot.mu.Unlock()

	if _, ok := bot.guilds[guildid]; ok {
		return false
	}

	bot.guilds[guildid] = &Guild{
		id:                  guildid,
		channelId:           channelid,
		lastInformedGameIds: make(map[riotapi.Puuid]riotapi.GameId),
	}
	bot.database.AddGuild(guildid, channelid)
	return true
}

func (bot *Bot) guildChannelId(guildid string) (string, bool) {
	bot.mu.RLock()
	defer bot.mu.RUnlock()

	guild, ok := bot.guilds[guildid]
	if !ok {
		return "", false
	}

	return guild.channelId, true
}

func (bot *Bot) setGuildChannel(guildid string, channelid string) {
	bot.mu.Lock()
	defer bot.mu.Unlock()

	guild, ok := bot.guilds[guildid]
	if !ok {
		guild = &Guild{
			id:                  guildid,
			lastInformedGameIds: make(map[riotapi.Puuid]riotapi.GameId),
		}
		bot.guilds[guildid] = guild
	}

	guild.channelId = channelid
	bot.database.SetChannel(guildid, channelid)
}

func (bot *Bot) isPlayerRegisteredInGuild(puuid riotapi.Puuid, guildid string) bool {
	bot.mu.RLock()
	defer bot.mu.RUnlock()

	guild, ok := bot.guilds[guildid]
	if !ok {
		return false
	}
	_, ok = guild.lastInformedGameIds[puuid]
	return ok
}

func (bot *Bot) addPlayerToGuild(puuid riotapi.Puuid, guildid string) bool {
	bot.mu.Lock()
	defer bot.mu.Unlock()

	guild, ok := bot.guilds[guildid]
	if !ok {
		return false
	}
	if _, ok := guild.lastInformedGameIds[puuid]; ok {
		return false
	}

	if _, ok := bot.players[puuid]; !ok {
		player := Player{id: puuid}
		player.StopWatch.Timeout = bot.offlineTimeout
		bot.players[puuid] = &player
	}
	guild.lastInformedGameIds[puuid] = 0
	bot.database.AddPlayerToGuild(puuid, guildid)

	return true
}

func (bot *Bot) removePlayerFromGuild(puuid riotapi.Puuid, guildid string) (bool, bool) {
	bot.mu.Lock()
	defer bot.mu.Unlock()

	guild, ok := bot.guilds[guildid]
	if !ok {
		return false, false
	}
	if _, ok := guild.lastInformedGameIds[puuid]; !ok {
		return false, false
	}

	delete(guild.lastInformedGameIds, puuid)
	bot.database.RemovePlayerFromGuild(puuid, guildid)

	for _, guild := range bot.guilds {
		if _, ok := guild.lastInformedGameIds[puuid]; ok {
			return true, false
		}
	}

	delete(bot.players, puuid)
	return true, true
}

func (bot *Bot) guildPuuids(guildid string) []riotapi.Puuid {
	bot.mu.RLock()
	defer bot.mu.RUnlock()

	guild, ok := bot.guilds[guildid]
	if !ok {
		return nil
	}

	puuids := make([]riotapi.Puuid, 0, len(guild.lastInformedGameIds))
	for puuid := range guild.lastInformedGameIds {
		puuids = append(puuids, puuid)
	}
	return puuids
}

func (bot *Bot) registeredPuuids() map[riotapi.Puuid]struct{} {
	bot.mu.RLock()
	defer bot.mu.RUnlock()

	puuids := make(map[riotapi.Puuid]struct{}, len(bot.players))
	for puuid := range bot.players {
		puuids[puuid] = struct{}{}
	}
	return puuids
}

func (bot *Bot) playerCheckStates() []playerCheckState {
	bot.mu.RLock()
	defer bot.mu.RUnlock()

	states := make([]playerCheckState, 0, len(bot.players))
	for _, player := range bot.players {
		stopped, elapsed := player.StopWatch.Stopped()
		states = append(states, playerCheckState{
			puuid:   player.id,
			stopped: stopped,
			elapsed: elapsed,
		})
	}
	return states
}

func (bot *Bot) startPlayerStopwatch(puuid riotapi.Puuid) bool {
	bot.mu.Lock()
	defer bot.mu.Unlock()

	player, ok := bot.players[puuid]
	if !ok {
		return false
	}

	player.StopWatch.Start()
	return true
}

func (bot *Bot) updatePlayerCheckTimeout(puuid riotapi.Puuid, online bool) bool {
	bot.mu.Lock()
	defer bot.mu.Unlock()

	player, ok := bot.players[puuid]
	if !ok {
		return false
	}

	return player.UpdateCheckTimeout(online, bot.offlineThreshold, bot.onlineTimeout, bot.offlineTimeout)
}

func (bot *Bot) guildNotificationTargets(puuid riotapi.Puuid, gameid riotapi.GameId) []guildNotificationTarget {
	bot.mu.RLock()
	defer bot.mu.RUnlock()

	targets := []guildNotificationTarget{}
	for _, guild := range bot.guilds {
		lastInformedGameId, ok := guild.lastInformedGameIds[puuid]
		if !ok || lastInformedGameId == gameid {
			continue
		}

		targets = append(targets, guildNotificationTarget{
			guildid:   guild.id,
			channelid: guild.channelId,
		})
	}
	return targets
}

func (bot *Bot) setLastInformedGameId(puuid riotapi.Puuid, guildid string, gameid riotapi.GameId) bool {
	bot.mu.Lock()
	defer bot.mu.Unlock()

	guild, ok := bot.guilds[guildid]
	if !ok {
		return false
	}
	if _, ok := guild.lastInformedGameIds[puuid]; !ok {
		return false
	}

	guild.lastInformedGameIds[puuid] = gameid
	bot.database.SetLastInformedGameId(puuid, guildid, gameid)
	return true
}
