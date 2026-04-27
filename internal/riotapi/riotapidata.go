package riotapi

func (riotapi *RiotApi) cachedRiotId(puuid Puuid) (RiotId, bool) {
	riotapi.mu.RLock()
	defer riotapi.mu.RUnlock()

	riotid, ok := riotapi.riotIds[puuid]
	return riotid, ok
}

func (riotapi *RiotApi) cachedPuuid(riotid RiotId) (Puuid, bool) {
	riotapi.mu.RLock()
	defer riotapi.mu.RUnlock()

	for puuid, cachedRiotId := range riotapi.riotIds {
		if cachedRiotId == riotid {
			return puuid, true
		}
	}

	return "", false
}

func (riotapi *RiotApi) cacheRiotId(puuid Puuid, riotid RiotId) bool {
	riotapi.mu.Lock()
	defer riotapi.mu.Unlock()

	_, existed := riotapi.riotIds[puuid]
	riotapi.riotIds[puuid] = riotid
	riotapi.database.SetRiotId(puuid, riotid)

	return existed
}

func (riotapi *RiotApi) riotIdsCount() int {
	riotapi.mu.RLock()
	defer riotapi.mu.RUnlock()

	return len(riotapi.riotIds)
}

func (riotapi *RiotApi) replaceRiotIds(riotIds map[Puuid]RiotId) {
	riotapi.mu.Lock()
	defer riotapi.mu.Unlock()

	riotapi.database.SetRiotIds(riotIds)
	riotapi.riotIds = riotIds
}

func (riotapi *RiotApi) championsLoaded() bool {
	riotapi.mu.RLock()
	defer riotapi.mu.RUnlock()

	return len(riotapi.champions) > 0
}

func (riotapi *RiotApi) cachedChampionName(championId ChampionId) (string, bool) {
	riotapi.mu.RLock()
	defer riotapi.mu.RUnlock()

	championName, ok := riotapi.champions[championId]
	return championName, ok
}

func (riotapi *RiotApi) replaceChampions(champions map[ChampionId]string) {
	riotapi.mu.Lock()
	defer riotapi.mu.Unlock()

	riotapi.database.SetChampions(champions)
	riotapi.champions = champions
}

func (riotapi *RiotApi) cachedSpectator(gameId GameId) (Spectator, bool) {
	riotapi.mu.RLock()
	defer riotapi.mu.RUnlock()

	spectator, ok := riotapi.spectatorCache[gameId]
	return spectator, ok
}

func (riotapi *RiotApi) cacheSpectator(gameId GameId, spectator Spectator) {
	riotapi.mu.Lock()
	defer riotapi.mu.Unlock()

	riotapi.spectatorCache[gameId] = spectator
}

func (riotapi *RiotApi) deleteSpectatorGames(gameIds map[GameId]struct{}) int {
	riotapi.mu.Lock()
	defer riotapi.mu.Unlock()

	for gameId := range gameIds {
		delete(riotapi.spectatorCache, gameId)
	}

	return len(riotapi.spectatorCache)
}

// Get all the game ids where the provided player is participating
func (riotapi *RiotApi) GetGameIds(puuid Puuid) map[GameId]struct{} {

	gameIds := make(map[GameId]struct{})
	riotapi.mu.RLock()
	defer riotapi.mu.RUnlock()

	for gameId, spectator := range riotapi.spectatorCache {
		for _, team := range spectator.Teams {
			for _, participant := range team {
				if participant.Puuid == puuid {
					gameIds[gameId] = struct{}{}
				}
			}
		}
	}

	return gameIds
}

func (riotapi *RiotApi) currentVersion() string {
	riotapi.mu.RLock()
	defer riotapi.mu.RUnlock()

	return riotapi.version
}

func (riotapi *RiotApi) updateVersion(realmVersion string) {
	riotapi.mu.Lock()
	defer riotapi.mu.Unlock()

	riotapi.database.SetVersion(realmVersion)
	riotapi.version = realmVersion
	riotapi.champions = make(map[ChampionId]string)
}
