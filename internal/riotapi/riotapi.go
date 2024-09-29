package riotapi

import (
	"chanclol/internal/common"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"

	"github.com/rs/zerolog/log"
)

// Riot schema
const RIOT_SCHEMA = "https://%s.api.riotgames.com"

// Urls that help decide the version of the data dragon files to download
const VERSIONS_JSON = "https://ddragon.leagueoflegends.com/api/versions.json"
const REALM = "https://ddragon.leagueoflegends.com/realms/euw.json"

// Routes inside the riot API
const ROUTE_ACCOUNT_PUUID = "/riot/account/v1/accounts/by-riot-id/%s/%s"
const ROUTE_ACCOUNT_RIOT_ID = "/riot/account/v1/accounts/by-puuid/%s"
const ROUTE_SUMMONER = "/lol/summoner/v4/summoners/by-puuid/%s"
const ROUTE_LEAGUE = "/lol/league/v4/entries/by-summoner/%s"
const ROUTE_MASTERY = "/lol/champion-mastery/v4/champion-masteries/by-puuid/%s/by-champion/%d"
const ROUTE_SPECTATOR = "/lol/spectator/v5/active-games/by-summoner/%s"

// Dragon route to fetch info about champions
const ROUTE_CHAMPIONS = "http://ddragon.leagueoflegends.com/cdn/%s/data/en_US/champion.json"

type RiotApi struct {
	database       DatabaseRiotApi
	champions      map[ChampionId]string
	riotIds        map[Puuid]RiotId
	summonerIds    map[Puuid]SummonerId
	version        string
	proxy          common.Proxy
	spectatorCache map[GameId]Spectator
}

func NewRiotApi(dbFilename string, apiKey string, restrictions []common.Restriction) RiotApi {

	var riotapi RiotApi

	riotapi.database = CreatDatabaseRiotApi(dbFilename)
	riotapi.champions = riotapi.database.GetChampions()
	riotapi.riotIds = riotapi.database.GetRiotIds()
	riotapi.summonerIds = riotapi.database.GetSummonerIds()
	riotapi.version = riotapi.database.GetVersion()
	riotapi.proxy = common.NewProxy(map[string]string{"X-Riot-Token": apiKey}, restrictions)
	riotapi.spectatorCache = map[GameId]Spectator{}

	return riotapi
}

func (riotapi *RiotApi) GetRiotId(puuid Puuid) (RiotId, error) {

	// Check cache
	if riotid, ok := riotapi.riotIds[puuid]; ok {
		return riotid, nil
	}
	log.Debug().Msg(fmt.Sprintf("Riot id for puuid %s is not in the cache", puuid))

	// Request
	url := fmt.Sprintf(RIOT_SCHEMA, "europe") + fmt.Sprintf(ROUTE_ACCOUNT_RIOT_ID, puuid)
	data := riotapi.request(url)
	if data == nil {
		return RiotId{}, fmt.Errorf("could not find riot id for puuid %s", puuid)
	}

	// Decode
	var riotid RiotId
	if err := json.Unmarshal(data, &riotid); err != nil {
		return RiotId{}, err
	}
	log.Debug().Msg(fmt.Sprintf("Found riot id %s for puuid %s", riotid, puuid))

	// Update cache
	riotapi.riotIds[puuid] = riotid
	riotapi.database.SetRiotId(puuid, riotid)
	return riotid, nil
}

func (riotapi *RiotApi) GetPuuid(riotid RiotId) (Puuid, error) {

	// Check cache
	for key, value := range riotapi.riotIds {
		if value == riotid {
			return key, nil
		}
	}

	// Request
	url := fmt.Sprintf(RIOT_SCHEMA, "europe") + fmt.Sprintf(ROUTE_ACCOUNT_PUUID, riotid.GameName, riotid.TagLine)
	data := riotapi.request(url)
	if data == nil {
		return "", fmt.Errorf("could not find puuid for riot id %s", riotid)
	}

	// Decode
	puuid, err := UnmarshalPuuid(data)
	if err != nil {
		return "", err
	}

	// Update cache
	// Take care here because maybe I have an old riot id that I need to update
	if _, ok := riotapi.riotIds[puuid]; ok {
		log.Debug().Msg(fmt.Sprintf("Updating riot id %s for puuid %s", riotid, puuid))
	} else {
		log.Debug().Msg(fmt.Sprintf("Found puuid %s for riot id %s", puuid, riotid))
	}
	riotapi.riotIds[puuid] = riotid

	// Database
	riotapi.database.SetRiotId(puuid, riotid)

	return puuid, nil
}

func (riotapi *RiotApi) GetChampionName(championId ChampionId) (string, error) {

	if len(riotapi.champions) == 0 {
		riotapi.getChampionData()
	}

	championName, ok := riotapi.champions[championId]
	if !ok {
		return "", fmt.Errorf("could not find champion name for champion id %d", championId)
	}

	return championName, nil
}

func (riotapi *RiotApi) GetMastery(puuid Puuid, championId ChampionId) (Mastery, error) {

	// Request
	url := fmt.Sprintf(RIOT_SCHEMA, "euw1") + fmt.Sprintf(ROUTE_MASTERY, puuid, championId)
	data := riotapi.request(url)
	if data == nil {
		return Mastery{}, fmt.Errorf("could not find mastery for puuid %s and champion id %d", puuid, championId)
	}

	return UnmarshalMastery(data)
}

func (riotapi *RiotApi) GetLeagues(puuid Puuid) ([]League, error) {

	// Summoner id
	summonerId, err := riotapi.getSummonerId(puuid)
	if err != nil {
		return nil, fmt.Errorf("could not find summoner id for puuid %s", puuid)
	}

	// Request
	url := fmt.Sprintf(RIOT_SCHEMA, "euw1") + fmt.Sprintf(ROUTE_LEAGUE, summonerId)
	data := riotapi.request(url)
	if data == nil {
		return nil, fmt.Errorf("no leagues found for puuid %s", puuid)
	}

	leagues, err := UnmarshalLeagues(data)
	if err != nil {
		return nil, err
	}

	return leagues, nil
}

func (riotapi *RiotApi) GetSpectator(puuid Puuid) (Spectator, error) {

	// Request
	url := fmt.Sprintf(RIOT_SCHEMA, "euw1") + fmt.Sprintf(ROUTE_SPECTATOR, puuid)
	data := riotapi.request(url)
	if data == nil {
		riotapi.trimSpectatorCache(puuid)
		return Spectator{}, fmt.Errorf("no spectator data found for puuid %s", puuid)
	}

	riotid, err := riotapi.GetRiotId(puuid)
	if err != nil {
		return Spectator{}, err
	}
	log.Info().Msg(fmt.Sprintf("%s is playing", riotid))

	// Decode game id and check if in cache
	gameId, err := UnmarshalGameId(data)
	if err != nil {
		return Spectator{}, err
	}
	if spectator, ok := riotapi.spectatorCache[gameId]; ok {
		log.Debug().Msg(fmt.Sprintf("Player %s is in a cached game", &riotid))
		return spectator, nil
	}

	// Not cached, so we need to decode the complete data
	// and make all the other requests
	// TODO: this function name makes me think I'm only decoding
	spectator, err := UnmarshalSpectator(data, riotapi)
	if err != nil {
		return Spectator{}, err
	}

	// Add game to the cache
	riotapi.spectatorCache[gameId] = spectator

	return spectator, nil
}

func (riotapi *RiotApi) getSummonerId(puuid Puuid) (SummonerId, error) {

	// Check cache
	summonerId, ok := riotapi.summonerIds[puuid]
	if ok {
		return summonerId, nil
	}

	// Request
	url := fmt.Sprintf(RIOT_SCHEMA, "euw1") + fmt.Sprintf(ROUTE_SUMMONER, puuid)
	data := riotapi.request(url)
	if data == nil {
		return "", fmt.Errorf("could not find summoner id for puuid %s", puuid)
	}
	var raw struct{ Id SummonerId }
	if json.Unmarshal(data, &raw) != nil {
		return "", fmt.Errorf("summoner id not found among received data")
	}
	summonerId = raw.Id
	log.Debug().Msg(fmt.Sprintf("Found summoner id %s for puuid %s", summonerId, puuid))

	// Update cache
	riotapi.summonerIds[puuid] = summonerId
	riotapi.database.SetSummonerId(puuid, summonerId)
	return summonerId, nil
}

func (riotapi *RiotApi) getChampionData() error {

	// Request
	url := fmt.Sprintf(ROUTE_CHAMPIONS, riotapi.version)
	data := riotapi.request(url)
	if data == nil {
		return fmt.Errorf("could not request champion data")
	}

	// Extract
	var raw struct {
		Data map[string]struct {
			Key string
			Id  string
		}
	}
	if json.Unmarshal(data, &raw) != nil {
		return fmt.Errorf("champion data in response is not correctly formatted")
	}

	// Update cache
	for _, champion := range raw.Data {
		if championId, err := strconv.Atoi(champion.Key); err != nil {
			return fmt.Errorf("champion id is not correctly formatted in response: %s", champion.Key)
		} else {
			riotapi.champions[ChampionId(championId)] = champion.Id
		}
	}

	// Database
	riotapi.database.SetChampions(riotapi.champions)

	return nil
}

func (riotapi *RiotApi) trimSpectatorCache(puuid Puuid) {

	gameIds := riotapi.GetGameIds(puuid)
	for gameId := range gameIds {
		delete(riotapi.spectatorCache, gameId)
	}
	if len(gameIds) > 0 {
		log.Info().Msg(fmt.Sprintf("Spectator cache trimmed to %d elements", len(riotapi.spectatorCache)))
	}
}

// Get all the game ids where the provided player is participating
func (riotapi *RiotApi) GetGameIds(puuid Puuid) map[GameId]struct{} {

	gameIds := make(map[GameId]struct{})
	for gameId, spectator := range riotapi.spectatorCache {
		for _, team := range spectator.Teams {
			for _, participant := range team {
				if participant.Puuid == puuid {
					gameIds[gameId] = struct{}{}
				}
			}
		}
	}

	if len(gameIds) > 1 {
		log.Error().Msg(fmt.Sprintf("Found %d game ids for puuid %s in the cache", len(gameIds), puuid))
	}

	return gameIds
}

func (riotapi *RiotApi) request(url string) []byte {

	vital := !strings.Contains(url, fmt.Sprintf(ROUTE_SPECTATOR, ""))
	log.Debug().Msg(fmt.Sprintf("Requesting to url %s", url))
	return riotapi.proxy.Request(url, vital)
}

func (riotapi *RiotApi) Housekeeping(puuidsToKeep map[Puuid]struct{}) {

	// Check patch version
	if riotapi.checkPatchVersion() != nil {
		log.Info().Msg("Could not check patch version")
		return
	}

	log.Info().Msg(fmt.Sprintf("Current number of riot ids: %d", len(riotapi.riotIds)))
	log.Info().Msg(fmt.Sprintf("Current number of summoner ids: %d", len(riotapi.summonerIds)))
	log.Info().Msg(fmt.Sprintf("Keeping %d puuids", len(puuidsToKeep)))

	// Purge my memory first
	// - remove all the riot ids
	// - add the riot ids that we need to keep, with the latest values provided by riot
	// - remove the summoner ids that are not needed
	riotapi.riotIds = make(map[Puuid]RiotId, len(puuidsToKeep))
	for puuid := range puuidsToKeep {

		// Get a new riot id and add to the map
		riotid, err := riotapi.GetRiotId(puuid)
		if err != nil {
			log.Error().Err(err)
			continue
		}

		riotapi.riotIds[puuid] = riotid
	}

	for puuid := range riotapi.summonerIds {
		if _, ok := puuidsToKeep[puuid]; !ok {
			delete(riotapi.summonerIds, puuid)
		}
	}

	// Send the final values to the database
	riotapi.database.SetRiotIds(riotapi.riotIds)
	riotapi.database.SetSummonerIds(riotapi.summonerIds)
}

// Fetches the latest version of the data dragon available, and checks the version
// is up in EUW.
// If the internal data is on an old version, it will force redownload when needed
func (riotapi *RiotApi) checkPatchVersion() error {

	// Check the versions.json file for the latest version
	url := VERSIONS_JSON
	data := riotapi.request(url)
	if data == nil {
		return fmt.Errorf("could not request file %s", VERSIONS_JSON)
	}
	// unmarshal
	var versions []string
	if json.Unmarshal(data, &versions) != nil {
		return fmt.Errorf("%s file does not have the expected content", VERSIONS_JSON)
	}
	latestVersion := versions[0]
	log.Info().Msg(fmt.Sprintf("Latest patch available in dd is %s", latestVersion))

	// Check which version the EUW is sitting on
	url = REALM
	data = riotapi.request(url)
	if data == nil {
		return fmt.Errorf("could not request file %s", REALM)
	}
	// unmarshal
	var realmVersion string
	{
		var realmsEuw struct{ Dd string }
		if json.Unmarshal(data, &realmsEuw) != nil {
			return fmt.Errorf("%s file does not have the expected content", REALM)
		}
		realmVersion = realmsEuw.Dd
	}
	log.Info().Msg(fmt.Sprintf("Realm patch version for EUW is %s", realmVersion))

	// The EUW version should at least exist among the overall versions
	var found bool = false
	for _, version := range versions {
		if version == realmVersion {
			found = true
			break
		}
	}
	if !found {
		return fmt.Errorf("EUW realm version %s was not found among the dd version", realmVersion)
	}

	// The EUW realm version is defined and exists among the versions,
	// so the new version for this API is clear
	// Do some logging
	if realmVersion == latestVersion {
		log.Info().Msg("EUW realm is on the latest version")
	} else {
		log.Info().Msg(fmt.Sprintf("EUW realm is on version %s while the latest version is %s", realmVersion, latestVersion))
	}

	// If the new version is different from the one currently in use,
	// invalidate my data to redownload when needed
	if riotapi.version != realmVersion {
		log.Info().Msg(fmt.Sprintf("Internal version (%s) is not in line with new version (%s)", riotapi.version, realmVersion))
		riotapi.version = realmVersion
		riotapi.database.SetVersion(realmVersion)
		riotapi.champions = make(map[ChampionId]string)
	} else {
		log.Info().Msg("Internal version is in line with the new version. Nothing to do")
	}

	return nil

}
