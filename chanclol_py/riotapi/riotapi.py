import logging

import riotapi.proxy as proxy
from database.database_riotapi import DatabaseRiotApi
from riot_id import RiotId
from riotapi.league import League
from riotapi.spectator import Spectator
from riotapi.mastery import Mastery

logger = logging.getLogger(__name__)

# These are the queues we care about, with the names we will be using
RELEVANT_QUEUES = {"RANKED_SOLO_5x5": "R. Solo", "RANKED_FLEX_SR": "R. Flex"}

# Several routes
# Riot schema
RIOT_SCHEMA = "https://{routing}.api.riotgames.com"
# Urls that help decide the version of the data dragon files to download
VERSIONS_JSON = "https://ddragon.leagueoflegends.com/api/versions.json"
REALM = "https://ddragon.leagueoflegends.com/realms/euw.json"
# Routes inside the riot API
ROUTE_ACCOUNT_PUUID = "/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
ROUTE_ACCOUNT_RIOT_ID = "/riot/account/v1/accounts/by-puuid/{puuid}"
ROUTE_SUMMONER = "/lol/summoner/v4/summoners/by-puuid/{puuid}"
ROUTE_LEAGUE = "/lol/league/v4/entries/by-summoner/{summoner_id}"
ROUTE_MASTERY = "/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champion_id}"
ROUTE_SPECTATOR = "/lol/spectator/v5/active-games/by-summoner/{puuid}"
# Dragon route to fetch info about champions
ROUTE_CHAMPIONS = (
    "http://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
)


class RiotApi:

    def __init__(
        self,
        key: str,
        database_filename: str,
        restrictions: list[dict],
    ):

        # A database managed by this class to serve as cache
        self.database: DatabaseRiotApi = DatabaseRiotApi(database_filename)
        # Relation between champion ids and champion names
        self.champions: dict[int, str] = self.database.get_champions()
        # Relation between puuids and riot ids
        self.riot_ids: dict[str, RiotId] = self.database.get_riot_ids()
        # Relation between puuids and summoner ids
        self.summoner_ids: dict[str, str] = self.database.get_summoner_ids()
        # Version of the Riot patch
        self.version: str = self.database.get_version()
        # The proxy will handle the requests for me
        self.proxy: proxy.Proxy = proxy.Proxy(key, restrictions)
        # Cache for spectator data
        self.spectator_cache: dict[int, Spectator] = {}

    # Return the puuid provided a riot id
    async def get_puuid(self, riot_id: RiotId) -> str | None:

        # Check if the puuid is cached
        for puuid in self.riot_ids:
            if self.riot_ids[puuid] == riot_id:
                return puuid

        # Make a request if not
        url = RIOT_SCHEMA.format(routing="europe") + ROUTE_ACCOUNT_PUUID.format(
            game_name=riot_id.game_name, tag_line=riot_id.tag_line
        )
        data = await self.request(url)
        if not data:
            logger.debug(f"No puuid found for riot id {riot_id}")
            return None

        # Keep a copy of the puuid for later
        puuid = data["puuid"]
        if puuid in self.riot_ids:
            logger.warning(
                f"Puuid {puuid} corresponds to riot ids {self.riot_ids[puuid]} and {riot_id}"
            )
            logger.warning("Keeping the latter as it is more recent")
        else:
            logger.debug(f"Caching riot id {riot_id} for puuid {puuid}")
        self.riot_ids[puuid] = riot_id
        self.database.add_riot_id(puuid, riot_id)

        return puuid

    async def get_riot_id(self, puuid: str) -> RiotId | None:

        # Check if cached
        if puuid in self.riot_ids:
            return self.riot_ids[puuid]

        # Make the request
        url = RIOT_SCHEMA.format(routing="europe") + ROUTE_ACCOUNT_RIOT_ID.format(
            puuid=puuid
        )
        data = await self.request(url)
        if not data:
            logger.error(f"Could not find riot id for puuid {puuid}")
            return None
        riot_id = RiotId(data["gameName"], data["tagLine"])

        # Save for later
        self.riot_ids[puuid] = riot_id
        self.database.add_riot_id(puuid, riot_id)

        return riot_id

    # Return the summoner id provided a puuid. This value will be useful to
    # access the league API
    async def get_summoner_id(self, puuid: str) -> str | None:

        # Try to find the value in the cache
        if puuid in self.summoner_ids:
            return self.summoner_ids[puuid]

        # Directly make the request
        url = RIOT_SCHEMA.format(routing="euw1") + ROUTE_SUMMONER.format(puuid=puuid)
        data = await self.request(url)
        if not data:
            logger.info(f"No summoner id found for puuid {puuid}")
            return None

        # Keep in cache
        summoner_id = data["id"]
        if puuid in self.summoner_ids and self.summoner_ids[puuid] != summoner_id:
            logger.warning(
                f"Update summoner id for puuid {puuid} from {self.summoner_ids[puuid]} to {summoner_id}"
            )
        elif not puuid in self.summoner_ids:
            logger.debug(f"Caching summoner id {summoner_id} for puuid {puuid}")
        self.summoner_ids[puuid] = summoner_id
        self.database.add_summoner_id(puuid, summoner_id)

        return summoner_id

    # Return all the League info for the provided summoner id.
    # The league info is a list of objects, one for each of the queues for which
    # the player has been placed. If the list is empty, the player is not placed.
    async def get_leagues(self, puuid: str) -> list[League]:

        # First get the corresponding summoner id
        summoner_id = await self.get_summoner_id(puuid)
        if not puuid:
            return []

        url = RIOT_SCHEMA.format(routing="euw1") + ROUTE_LEAGUE.format(
            summoner_id=summoner_id
        )
        data = await self.request(url)
        if not data:
            logger.info(f"No league data found for summoner id {summoner_id}")
            return []

        result = []
        for relevant_queue in RELEVANT_QUEUES:
            for league_data in data:
                if league_data["queueType"] == relevant_queue:
                    league = League.create(league_data, RELEVANT_QUEUES[relevant_queue])
                    if league:
                        result.append(league)
        return result

    # Return the mastery of the provided player with the provided champion
    async def get_mastery(self, puuid: str, champion_id: int) -> Mastery | None:

        url = RIOT_SCHEMA.format(routing="euw1") + ROUTE_MASTERY.format(
            puuid=puuid, champion_id=champion_id
        )
        data = await self.request(url)
        if not data:
            logger.debug(
                f"No mastery found for puuid {puuid} and champion {champion_id}"
            )

        return Mastery.create(data)

    # Return information about the live game of the user provided (if any)
    async def get_spectator(self, puuid: str) -> Spectator | None:

        url = RIOT_SCHEMA.format(routing="euw1") + ROUTE_SPECTATOR.format(puuid=puuid)
        data = await self.request(url)
        if not data:
            logger.debug(f"No spectator data found for puuid {puuid}")
            self.trim_spectator_cache(puuid)
            return None
        else:
            riot_id = self.riot_ids[puuid]
            logger.debug(f"Player {riot_id} is in game")
            game_id = data["gameId"]
            # If we have this game cached, just return it
            cached_game_info = self.get_game_from_cache(game_id)
            if cached_game_info != None:
                logger.debug(f"Player {riot_id} is in an already cached game")
                return cached_game_info
            # If we do not have it cached, we need to make the complete request
            logger.info(f"Player {riot_id} is in a game not found in the cache")
            spectator = await Spectator.create(data, self)
            # Finally add the game to the cache if it's valid
            if spectator:
                self.spectator_cache[game_id] = spectator
            return spectator

    # The provided player has stopped playing, so remove the associated game id
    # from the internal list if there is any
    def trim_spectator_cache(self, puuid: str) -> None:

        game_ids_to_delete = self.get_game_ids_for_player(puuid)
        # If a game was found for this player, delete it from the cache
        for game_id in game_ids_to_delete:
            del self.spectator_cache[game_id]
        logger.info(f"Spectator cache trimmed to {len(self.spectator_cache)} elements")

    # Get all the game ids where the provided player is participating
    def get_game_ids_for_player(self, puuid: str) -> set[int]:

        game_ids = set()
        for spectator in self.spectator_cache.values():
            for team in spectator.teams.values():
                for participant in team:
                    if participant.puuid == puuid:
                        game_ids.add(spectator.game_id)
                        break
        return game_ids

    # Check if the info for game id provided already exists
    def get_game_from_cache(self, game_id: int) -> Spectator | None:

        if game_id in self.spectator_cache:
            logger.debug(f"Game id {game_id} has been found in the cache")
            return self.spectator_cache[game_id]
        else:
            logger.debug(f"Game id {game_id} has not been found in the cache")
            return None

    # Creates the internal data for champions
    async def request_champion_data(self):

        url = ROUTE_CHAMPIONS.format(version=self.version)
        data = await self.request(url)
        if not data:
            logger.error("No champions data found")
            return None

        # Keep a copy of the data
        for champion in data["data"].values():
            self.champions[int(champion["key"])] = champion["id"]
        self.database.set_champions(self.champions)

    # Return the champion name corresponding to a champion id
    async def get_champion_name(self, champion_id: int) -> str | None:

        if not self.champions or not champion_id in self.champions:
            await self.request_champion_data()

        if not champion_id in self.champions:
            logger.error(f"Could not find name of champion id {champion_id}")
            return None
        return self.champions[champion_id]

    # Purge the information I have in my database
    async def housekeeping(self, puuids_to_keep: list[str]) -> None:

        # Check patch version
        await self.check_patch_version()

        logger.info(f"Current number of riot ids: {len(self.riot_ids)}")
        logger.info(f"Current number of summoner ids: {len(self.summoner_ids)}")
        logger.info(f"Keeping {len(puuids_to_keep)} puuids")
        # Purge the values in memory:
        # * remove the puuids that are not needed
        # * update the needed ones with the latest values provided by riot
        for puuid in self.riot_ids:
            if not puuid in puuids_to_keep:
                self.riot_ids.pop(puuid)
            else:
                riot_id = await self.get_riot_id(puuid)
                if not riot_id:
                    logger.error(
                        f"No riot id found for puuid {puuid} while purging. Keeping old value. This may be a big problem..."
                    )
                else:
                    self.riot_ids[puuid] = riot_id
        for puuid in self.summoner_ids:
            if not puuid in puuids_to_keep:
                self.summoner_ids.pop(puuid)
            else:
                summoner_id = await self.get_summoner_id(puuid)
                if not summoner_id:
                    logger.error(
                        f"No summoner id found for puuid {puuid} while purging. Keeping old value. This may be a big problem..."
                    )
                else:
                    self.summoner_ids[puuid] = summoner_id
        # Send the final values to the file database
        self.database.set_riot_ids(self.riot_ids)
        self.database.set_summoner_ids(self.summoner_ids)

    # Make a request (forward it to the proxy, essentially)
    async def request(self, url: str) -> dict | None:

        # Decide if the request is vital or not
        vital = not ROUTE_SPECTATOR.format(puuid="") in url

        # Forward the request to the proxy
        return await self.proxy.request(url, vital)

    # Fetches the latest version of the data dragon available, and checks the version
    # is up in EUW. If the internal data is on an old version, force redownload
    async def check_patch_version(self) -> None:

        # Check the versions.json file for the latest version
        url = VERSIONS_JSON
        versions = await self.request(url)
        if not versions:
            logger.error("Could not find versions data")
            return
        latest_version = versions[0]
        logger.info(f"Latest patch available in dd is {latest_version}")

        # Check on which version the EUW is sitting
        url = REALM
        euw_realm = await self.request(url)
        if not euw_realm:
            logger.error("Could not find EUW realm")
            return
        realm_version = euw_realm["dd"]
        logger.info(f"Realm patch for EUW is {realm_version}")

        # The EUW version should at least exist in the overall versions
        if not realm_version in versions:
            raise ValueError(
                f"The EUW realm version {realm_version} has not been found in versions.json"
            )
        # In this case the new version for EUW is clear
        new_version = realm_version
        # Some logging
        if new_version == latest_version:
            logger.info(f"EUW realm is on the latest version {latest_version}")
        else:
            logger.warning(
                f"EUW realm is on version {realm_version} while the latest version is {latest_version}"
            )

        # If we need to update the internal version, force an update of the internal data
        if self.version != new_version:
            logger.info(
                f"Internal version ({self.version}) is not in line with {new_version}"
            )
            self.version = new_version
            self.database.set_version(self.version)
            self.champions.clear()
        else:
            logger.info(f"Internal version is in line with {new_version}")
