package riotapi

import (
	"chanclol/internal/common"
	"chanclol/internal/database"
	"chanclol/internal/types"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
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
	database       database.DatabaseRiotApi
	champions      map[types.ChampionId]string
	riotIds        map[types.Puuid]types.RiotId
	summonerIds    map[types.Puuid]types.SummonerId
	version        string
	proxy          common.Proxy
	spectatorCache map[types.GameId]types.Spectator
}

func CreateRiotApi(dbFilename string, apiKey string, restrictions []common.Restriction) RiotApi {

	var riotapi RiotApi

	riotapi.database = database.CreatDatabaseRiotApi(dbFilename)
	riotapi.champions = riotapi.database.GetChampions()
	riotapi.riotIds = riotapi.database.GetRiotIds()
	riotapi.summonerIds = riotapi.database.GetSummonerIds()
	riotapi.version = riotapi.database.GetVersion()
	riotapi.proxy = common.CreateProxy(map[string]string{"X-Riot-Token": apiKey}, restrictions)
	riotapi.spectatorCache = map[types.GameId]types.Spectator{}

	return riotapi
}

func (riotapi *RiotApi) GetRiotId(puuid types.Puuid) (types.RiotId, error) {

	// Check cache
	riotid, ok := riotapi.riotIds[puuid]
	if ok {
		return riotid, nil
	}

	// Request
	url := fmt.Sprintf(RIOT_SCHEMA, "europe") + fmt.Sprintf(ROUTE_ACCOUNT_RIOT_ID, puuid)
	data := riotapi.request(url)
	if data == nil {
		return types.RiotId{}, fmt.Errorf("could not find riot id for puuid %s", puuid)
	}

	// Decode
	riotid, err := DecodeRiotId(data)
	if err != nil {
		return riotid, err
	}
	fmt.Printf("found riot id %s for puuid %s", riotid, puuid)

	// Update cache
	riotapi.riotIds[puuid] = riotid
	riotapi.database.SetRiotId(puuid, riotid)
	return riotid, nil
}

func (riotapi *RiotApi) GetPuuid(riotid types.RiotId) (types.Puuid, error) {

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
	puuid, err := DecodePuuid(data)
	if err != nil {
		return "", err
	}

	// Update cache
	// Take care here because maybe I have an old riot id that I need to update
	if _, ok := riotapi.riotIds[puuid]; ok {
		fmt.Printf("Updating riot id %s for puuid %s", riotid, puuid)
	} else {
		fmt.Printf("Found puuid %s for riot id %s", puuid, riotid)
	}
	riotapi.riotIds[puuid] = riotid

	// Database
	riotapi.database.SetRiotId(puuid, riotid)

	return puuid, nil
}

func (riotapi *RiotApi) GetChampionName(championId types.ChampionId) (string, error) {

	if len(riotapi.champions) == 0 {
		riotapi.getChampionData()
	}

	championName, ok := riotapi.champions[championId]
	if !ok {
		return "", fmt.Errorf("could not find champion name for champion id %d", championId)
	}

	return championName, nil
}

func (riotapi *RiotApi) GetMastery(puuid types.Puuid, championId types.ChampionId) (types.Mastery, error) {

	// Request
	url := fmt.Sprintf(RIOT_SCHEMA, "euw1") + fmt.Sprintf(ROUTE_MASTERY, puuid, championId)
	data := riotapi.request(url)
	if data == nil {
		return types.Mastery{}, fmt.Errorf("could not find mastery for puuid %s and champion id %d", puuid, championId)
	}

	return DecodeMastery(data)
}

func (riotapi *RiotApi) GetLeagues(puuid types.Puuid) ([]types.League, error) {

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

	leagues, err := DecodeLeagues(data)
	if err != nil {
		return nil, err
	}

	return leagues, nil
}

func (riotapi *RiotApi) GetSpectator(puuid types.Puuid) (types.Spectator, error) {

	// Request
	url := fmt.Sprintf(RIOT_SCHEMA, "euw1") + fmt.Sprintf(ROUTE_SPECTATOR, puuid)
	data := riotapi.request(url)
	if data == nil {
		riotapi.trimSpectatorCache(puuid)
		return types.Spectator{}, fmt.Errorf("no spectator data found for puuid %s", puuid)
	}

	riotid, err := riotapi.GetRiotId(puuid)
	if err != nil {
		return types.Spectator{}, fmt.Errorf("player with puuid %s is playing but their riot id is not found", puuid)
	}
	fmt.Printf("%s is playing", riotid)

	// Decode game id and check if in cache
	gameId, err := DecodeGameId(data)
	if err != nil {
		return types.Spectator{}, err
	}
	if spectator, ok := riotapi.spectatorCache[gameId]; ok {
		fmt.Printf("Player %s is in a cached game", &riotid)
		return spectator, nil
	}

	// Not cached, so we need to decode the complete data
	// and make all the other requests
	// TODO: this function name makes me think I'm only decoding
	spectator, err := DecodeSpectator(data, riotapi)
	if err != nil {
		return types.Spectator{}, err
	}

	// Add game to the cache
	riotapi.spectatorCache[gameId] = spectator

	return spectator, nil
}

func (riotapi *RiotApi) getSummonerId(puuid types.Puuid) (types.SummonerId, error) {

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
	var raw struct{ Id types.SummonerId }
	if json.Unmarshal(data, &raw) != nil {
		return "", fmt.Errorf("summoner id not found among received data")
	}
	summonerId = raw.Id
	fmt.Printf("Found summoner id %s for puuid %s", summonerId, puuid)

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
			riotapi.champions[types.ChampionId(championId)] = champion.Id
		}
	}

	// Database
	riotapi.database.SetChampions(riotapi.champions)

	return nil
}

func (riotapi *RiotApi) trimSpectatorCache(puuid types.Puuid) {

}

func (riotapi *RiotApi) request(url string) []byte {

	vital := !strings.Contains(url, fmt.Sprintf(ROUTE_SPECTATOR, ""))
	return riotapi.proxy.Request(url, vital)
}
