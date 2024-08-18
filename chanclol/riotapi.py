import logging
import time

import proxy

logger = logging.getLogger(__name__)

# These are the queues we care about, with the names we will be using
relevant_queues = {"RANKED_SOLO_5x5": "R. Solo", "RANKED_FLEX_SR": "R. Flex"}


class League:
    # Information returned, for a specific player and for a specific
    # queue, containing its current ranked position in that queue

    def __init__(self, data, queue_type):
        if not data:
            return None
        self.queue_type = queue_type
        self.tier = data["tier"]
        self.rank = data["rank"]
        self.lps = data["leaguePoints"]
        self.wins = data["wins"]
        self.losses = data["losses"]
        total_games = self.wins + self.losses
        self.win_rate = int(self.wins / (total_games) * 100) if total_games != 0 else 0


class Mastery:
    # Information about how good is a player with a certain champion

    def __init__(self, data):
        if not data:
            return None
        # Mastery level
        self.level = data["championLevel"]
        # lastPlayTime is in Unix milliseconds
        time_in_seconds = time.time()
        self.days_since_last_played = round(
            (time_in_seconds - data["lastPlayTime"] / 1000) / 3600 / 24
        )


class Spectator:
    # Information about a live game

    def __init__(self):
        self.game_id = None
        self.game_length_minutes = None
        self.teams = {}


class Participant:
    # Information about a participant in a spectator (live) game

    def __init__(self):
        self.riot_id = None
        self.puuid = None
        self.champion_name = None
        self.mastery = None
        self.league = None


class RiotApi:
    def __init__(self, api_key, restrictions):
        # Riot schema
        self.riot_schema = "https://{routing}.api.riotgames.com"
        # Urls that help decide the version of the data dragon files to download
        self.versions_json = "https://ddragon.leagueoflegends.com/api/versions.json"
        self.realm = "https://ddragon.leagueoflegends.com/realms/euw.json"
        self.version = ""
        # Routes inside the riot API
        self.route_account_puuid = (
            "/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        )
        self.route_account_riot_id = "/riot/account/v1/accounts/by-puuid/{puuid}"
        self.route_summoner = "/lol/summoner/v4/summoners/by-puuid/{puuid}"
        self.route_league = "/lol/league/v4/entries/by-summoner/{summoner_id}"
        self.route_mastery = "/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champion_id}"
        self.route_spectator = "/lol/spectator/v5/active-games/by-summoner/{puuid}"
        # Dragon route to fetch info about champions
        self.route_champions = (
            "http://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
        )
        self.data_champions = {}
        # Dictionary storing riot ids for each puuid
        self.riot_ids = {}
        # Dictionary storing summoner ids for each puuid
        self.summoner_ids = {}
        # The proxy will handle the requests for me
        self.proxy = proxy.Proxy(api_key, restrictions)
        # Riot API will have a database (it will be set by the bot)
        self.database = None
        # Cache for spectator data
        self.spectator_cache = {}

    # Return the puuid provided a riot id
    async def get_puuid(self, riot_id):

        # Check if the puuid is cached
        for puuid in self.riot_ids:
            if self.riot_ids[puuid] == riot_id:
                return puuid

        # Make a request if not
        url = self.riot_schema.format(
            routing="europe"
        ) + self.route_account_puuid.format(game_name=riot_id[0], tag_line=riot_id[1])
        data = await self.request(url)
        if not data:
            logger.debug(f"No puuid found for riot id {self.print_riot_id(riot_id)}")
            return None

        # Keep a copy of the puuid for later
        puuid = data["puuid"]
        if puuid in self.riot_ids:
            logger.warning(
                f"Puuid {puuid} corresponds to riot ids {self.print_riot_id(self.riot_ids[puuid])} and {self.print_riot_id(riot_id)}"
            )
            logger.warning("Keeping the latter as it is more recent")
        logger.debug(f"Caching riot id {self.print_riot_id(riot_id)} for puuid {puuid}")
        self.riot_ids[puuid] = riot_id
        self.database.add_riot_id(puuid, riot_id)

        return puuid

    # Return all the League info for the provided summoner id.
    # The league info is a list of objects, one for each of the queues for which
    # the player has been placed. If the list is empty, the player is not placed.
    async def get_league(self, puuid):

        # First get the corresponding summoner id
        summoner_id = await self.get_summoner_id(puuid)
        if not puuid:
            return None

        url = self.riot_schema.format(routing="euw1") + self.route_league.format(
            summoner_id=summoner_id
        )
        data = await self.request(url)
        if not data:
            logger.info(f"No league data found for summoner id {summoner_id}")

        return self.create_league(data)

    # Return the mastery of the provided player with the provided champion
    async def get_mastery(self, puuid, champion_id):

        url = self.riot_schema.format(routing="euw1") + self.route_mastery.format(
            puuid=puuid, champion_id=champion_id
        )
        data = await self.request(url)
        if not data:
            logger.debug(
                f"No mastery found for puuid {puuid} and champion {champion_id}"
            )

        return Mastery(data)

    # Return information about the live game of the user provided (if any)
    async def get_spectator(self, puuid):

        url = self.riot_schema.format(routing="euw1") + self.route_spectator.format(
            puuid=puuid
        )
        data = await self.request(url)
        if not data:
            logger.debug(f"No spectator data found for puuid {puuid}")
            self.trim_active_game_cache(puuid)
            return None
        else:
            riot_id = self.print_riot_id(self.riot_ids[puuid])
            logger.debug(f"Player {riot_id} is in game")
            game_id = data["gameId"]
            # If we have this game cached, just return it
            cached_game_info = self.get_game_from_cache(game_id)
            if cached_game_info != None:
                logger.debug(f"Player {riot_id} is in an already cached game")
                return cached_game_info
            # If we do not have it cached, we need to make the complete request
            logger.info(f"Player {riot_id} is in a game not found in the cache")
            active_game = await self.create_spectator(data)
            # Finally add the game to the cache if it's valid
            if active_game:
                self.spectator_cache[game_id] = active_game
            return active_game

    async def get_riot_id(self, puuid):
        if puuid in self.riot_ids:
            return self.riot_ids[puuid]

        # Make the request
        url = self.riot_schema.format(
            routing="europe"
        ) + self.route_account_riot_id.format(puuid=puuid)
        data = await self.request(url)
        if not data:
            logger.error(f"Could not find riot id for puuid {puuid}")
            return None

        return (data["gameName"], data["tagLine"])

    # Return the summoner id provided a puuid. This value will be useful to
    # access the league API
    async def get_summoner_id(self, puuid):

        # Try to find the value in the cache
        if puuid in self.summoner_ids:
            return self.summoner_ids[puuid]

        # Directly make the request
        url = self.riot_schema.format(routing="euw1") + self.route_summoner.format(
            puuid=puuid
        )
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
        logger.debug(f"Caching summoner id {summoner_id} for puuid {puuid}")
        self.summoner_ids[puuid] = summoner_id
        self.database.add_summoner_id(puuid, summoner_id)

        return summoner_id

    # Print the riot id provided a game name and tag line
    def print_riot_id(self, riot_id):
        return f"'{riot_id[0]}#{riot_id[1]}'"

    # Create spectator information
    # Return value of not None means the player is in game
    async def create_spectator(self, data):

        if not data:
            return None

        spectator = Spectator()
        spectator.game_id = data["gameId"]
        spectator.game_length_minutes = round(data["gameLength"] / 60)
        # Create the list of all the provided team ids
        team_ids = list(
            set([participant["teamId"] for participant in data["participants"]])
        )
        # Fill in the teams
        for team_id in team_ids:
            spectator.teams[team_id] = []
            for participant_data in data["participants"]:
                if participant_data["teamId"] == team_id:
                    participant = await self.create_participant(participant_data)
                    if not participant:
                        logger.error(
                            f"Could not create participant while preparing spectator data"
                        )
                        return None
                    spectator.teams[team_id].append(participant)
        return spectator

    # Create a participant from the spectator participant data.
    # This function may make additional requests
    async def create_participant(self, data):

        if not data:
            return None

        participant = Participant()
        # puuid
        puuid = data["puuid"]
        participant.puuid = puuid
        # riot id
        participant.riot_id = await self.get_riot_id(puuid)
        # Champion name
        champion_id = data["championId"]
        participant.champion_name = await self.get_champion_name(champion_id)
        if not participant.champion_name:
            return None
        # Champion mastery
        participant.mastery = await self.get_mastery(puuid, champion_id)
        # League
        participant.league = await self.get_league(puuid)
        return participant

    def create_league(self, data):
        if not data:
            return None

        result = []
        for relevant_queue in relevant_queues:
            for league_data in data:
                if league_data["queueType"] == relevant_queue:
                    league = League(league_data, relevant_queues[relevant_queue])
                    result.append(league)
        return result

    # The provided player has stopped playing, so remove the associated game id
    # from the internal list if there is any
    def trim_active_game_cache(self, puuid):
        game_id_to_delete = self.get_game_id_for_player(puuid)
        # If a game was found for this player, delete it from the cache
        if game_id_to_delete != None:
            del self.spectator_cache[game_id_to_delete]
            logger.info(
                f"Spectator cache has been trimmed to {len(self.spectator_cache)} elements"
            )

    # Get the game id that corresponds to the provided player, if any
    def get_game_id_for_player(self, puuid):
        for active_game in self.spectator_cache.values():
            for team in active_game.teams.values():
                for participant in team:
                    if participant.puuid == puuid:
                        return active_game.game_id
        return None

    # Check if the info for game id provided already exists
    def get_game_from_cache(self, game_id):
        if game_id in self.spectator_cache:
            logger.debug(f"Game id {game_id} has been found in the cache")
            return self.spectator_cache[game_id]
        else:
            logger.debug(f"Game id {game_id} has not been found in the cache")
            return None

    # Creates the internal data for champions
    async def request_champion_data(self):

        url = self.route_champions.format(version=self.version)
        data = await self.request(url)
        if not data:
            logger.error("No champions data found")
            return None

        # Keep a copy of the data
        for champion in data["data"].values():
            self.data_champions[int(champion["key"])] = champion["id"]
        self.database.set_champions(self.data_champions)

    # Return the champion name corresponding to a champion id
    async def get_champion_name(self, champion_id):

        if not self.data_champions:
            await self.request_champion_data()

        if not champion_id in self.data_champions:
            logger.error(f"Could not find name of champion id {champion_id}")
            return None
        return self.data_champions[champion_id]

    # The bot sends the database once initialised. Take the time here to
    # see if the database already has useful information for us
    def set_database(self, database):
        self.database = database
        self.champions = self.database.get_champions()
        self.riot_ids = self.database.get_riot_ids()
        self.summoner_ids = self.database.get_summoner_ids()
        self.version = self.database.get_version()

    # Purge the information I have in my database
    async def purge(self, puuids_to_keep):

        # TODO: this function does not actually purge

        logger.info(f"Current number of riot ids: {len(self.riot_ids)}")
        logger.info(f"Current number of summoner ids: {len(self.summoner_ids)}")
        logger.info(f"Keeping {len(puuids_to_keep)} puuids")
        # Purge the values in memory:
        # * remove the puuids that are not needed
        # * update the needed ones with the latest values provided by riot
        for puuid in [puuid for puuid in self.riot_ids]:
            if not puuid in puuids_to_keep:
                self.riot_ids.pop(puuid)
            else:
                riot_id = await self.get_riot_id(puuid)
                if not riot_id:
                    logger.error(
                        f"No riot id found for puuid {puuid} while purging. Keeping old value"
                    )
                self.riot_ids[puuid] = riot_id
        for puuid in [puuid for puuid in self.summoner_ids]:
            if not puuid in puuids_to_keep:
                self.summoner_ids.pop(puuid)
            else:
                summoner_id = await self.get_summoner_id(puuid)
                if not summoner_id:
                    logger.error(
                        f"No summoner id found for puuid {puuid} while purging. Keeping old value"
                    )
                self.summoner_ids[puuid] = summoner_id
        # Send the final values to the file database
        self.database.set_riot_ids(self.riot_ids)
        self.database.set_summoner_ids(self.summoner_ids)

    # Make a request (forward it to the proxy, essentially)
    async def request(self, url):

        # Decide if the request is vital or not
        vital = not self.route_spectator.format(puuid="") in url

        # Forward the request to the proxy
        return await self.proxy.request(url, vital)

    # Fetches the latest version of the data dragon available, and checks the version
    # is up in EUW. If the internal data is on an old version, force redownload
    async def check_patch_version(self):

        # Check the versions.json file for the latest version
        url = self.versions_json
        versions = await self.request(url)
        if not versions:
            logger.error("Could not find versions data")
            return
        latest_version = versions[0]
        logger.info(f"Latest patch available in dd is {latest_version}")

        # Check on which version the EUW is sitting
        url = self.realm
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
            self.data_champions.clear()
        else:
            logger.info(f"Internal version is in line with {new_version}")
