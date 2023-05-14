import requests
import time
import rate_limiter
import logging

logger = logging.getLogger(__name__)


class LeagueInfo:
    # Information returned, for a specific player and for a specific
    # queue, containing its current ranked position in that queue

    def __init__(self, response):
        if not response:
            return None
        self.queue_type = response['queueType']
        self.tier = response['tier']
        self.rank = response['rank']
        self.lps = response['leaguePoints']


class Participant:
    # Information about a participant in a live game

    def __init__(self):
        self.player_name = None
        self.player_id = None
        self.champion_name = None
        self.spell1_name = None
        self.spell2_name = None
        self.mastery = None


class InGameInfo:
    # Information about an on going game for a specific player

    def __init__(self):
        self.in_game = None
        self.game_id = None
        self.game_length_minutes = None
        self.teams = []


class MasteryInfo:
    # Information about how good is a player with a certain champion

    def __init__(self, response):
        # Flag indicating if mastery info is available for the player and champion combination
        self.available = response != None
        if not self.available:
            return
        # Mastery level
        self.level = response['championLevel']
        # lastPlayTime is in Unix milliseconds
        time_in_seconds = time.time()
        self.days_since_last_played = round((time_in_seconds -
                                             response['lastPlayTime'] / 1000) / 3600 / 24)


class Response:
    # Low level response returned by the Riot API
    def __init__(self, response):
        # I always expect to return an instance of the class
        self.status_code = None
        self.data = None
        if response == None:
            return
        # Update status code in case it is available
        self.status_code = response.status_code
        if self.status_code == 200:
            self.data = response.json()
        elif self.status_code == 429:
            logger.warning('Received 429: Riot is rate limiting requests')
        elif self.status_code == 404:
            logger.debug('Received 404: data not found')
        elif self.status_code == 403:
            logger.error(
                'Received 403: forbidden. Probably API key is not valid')
        else:
            logger.error(
                f'Unknown error connecting to Riot API: {response.json()}')


class RiotApi:
    def __init__(self, api_key):
        # Riot schema
        self.riot_schema = 'https://euw1.api.riotgames.com'
        # Variable that will hold the API key
        self.api_key = api_key
        # Routes inside the riot API
        self.route_summoner = '/lol/summoner/v4/summoners/by-name/'
        self.route_league = '/lol/league/v4/entries/by-summoner/'
        self.route_mastery = '/lol/champion-mastery/v4/champion-masteries/by-summoner/'
        self.route_mastery_by_champ = '/by-champion/'
        self.route_active_games = '/lol/spectator/v4/active-games/by-summoner/'
        # Dragon route to fetch info about the champions
        self.route_champions = 'http://ddragon.leagueoflegends.com/cdn/13.9.1/data/en_US/champion.json'
        self.data_champions = None
        # Dragon route to fetch info about spells
        self.route_spells = 'http://ddragon.leagueoflegends.com/cdn/13.9.1/data/en_US/summoner.json'
        self.data_spells = None
        # Dictionary of encrypted summoner ids as keys, and player names as values
        self.names = {}
        # Create a rate limiter that will give permissions to make requests to riot API
        # 100 requests in 2 minutes
        restriction1 = rate_limiter.Restriction(100, 2 * 60 * 1000)
        # 20 requests per second
        restriction2 = rate_limiter.Restriction(20, 1 * 1000)
        self.rate_limiter = rate_limiter.RateLimiter(
            [restriction1, restriction2])
        # Riot API will have a database (it will be set by the bot)
        self.database = None
        # Cache for active games
        self.active_game_cache = {}

    # Returns all the League info for the provided player id.
    # The league info is a list of objects, one for each of the queues for which
    # the player has been placed. If the list is empty, the player is not placed.
    async def get_league_info(self, player_id):

        # Build the request
        url = self.riot_schema + self.route_league + player_id
        header = self.build_api_header()
        if header == None:
            logger.error('Could not build the header for the request')
            return None

        # Make the request to the server
        response = await self._get(url, header)
        if response.status_code != 200:
            logger.error('Could not make a request to the Riot league API')
            return None

        # Prepare the final result
        result = []
        for league in response.data:
            result.append(LeagueInfo(league))
        return result

    # Returns the mastery of certain player with certain champion
    async def get_mastery_info(self, player_id, champion_id):

        # Build the request
        url = self.riot_schema + self.route_mastery + player_id
        url += self.route_mastery_by_champ + str(champion_id)
        header = self.build_api_header()
        if header == None:
            logger.error('Could not build the header for the request')
            return None

        # Make the request and check everything is OK
        response = await self._get(url, header)
        if response.status_code == 404:
            logger.info(
                f'Mastery was not found for this player {self.get_player_name(player_id)} and champion {champion_id} combination')
            return MasteryInfo(None)
        elif response.status_code != 200:
            logger.error(
                f'Error retrieving mastery for player {self.get_player_name(player_id)}')
            return None
        else:
            return MasteryInfo(response.data)

    # Returns information about ongoing games
    async def get_active_game_info(self, player_id):

        # Build the request
        url = self.riot_schema + self.route_active_games + player_id
        header = self.build_api_header()
        if header == None:
            logger.error('Could not build the header for the request')
            return None

        # Make the request and check everything is OK
        response = await self._get(url, header)
        player_name = self.get_player_name(player_id)
        if response.status_code == 404:
            logger.debug(f'Player {player_name} is not in game')
            self.trim_active_game_cache(player_id)
            return await self.create_in_game_info(None)
        elif response.status_code == 429:
            logger.warning('Rate limited')
            return None
        elif response.status_code != 200:
            logger.warning(
                'Could not make a request to the Riot active game API')
            return None
        else:
            logger.debug(f'Player {player_name} is in game')
            game_id = response.data['gameId']
            # If we have this game cached, just return it
            cached_game_info = self.get_game_from_cache(game_id)
            if cached_game_info != None:
                logger.debug(
                    f'Player {player_name} is in an already cached game')
                return cached_game_info
            # If we do not have it cached, we need to make the complete request
            logger.info(
                f'Player {player_name} is in a game not found in the cache')
            active_game = await self.create_in_game_info(response.data)
            # Finally add the game to the cache
            self.active_game_cache[game_id] = active_game
            return active_game

    # The provided player has stopped playing, so remove the associated game id
    # from the internal list if there is any
    def trim_active_game_cache(self, player_id):
        game_id_to_delete = self.get_game_id_for_player(player_id)
        # If a game was found for this player, delete it from the cache
        if game_id_to_delete != None:
            del self.active_game_cache[game_id_to_delete]
            logger.info(
                f'Active games cache has been trimmed to {len(self.active_game_cache)} elements')

    # Gets the game id that corresponds to the provided player, if any
    def get_game_id_for_player(self, player_id):
        for active_game in self.active_game_cache.values():
            for team in active_game.teams:
                for participant in team:
                    if participant.player_id == player_id:
                        return active_game.game_id
        return None

    # Check if the info for game id provided already exists
    def get_game_from_cache(self, game_id):
        if game_id in self.active_game_cache:
            logger.debug(f'Game id {game_id} has been found in the cache')
            return self.active_game_cache[game_id]
        else:
            logger.debug(f'Game id {game_id} has not been found in the cache')
            return None

    # Create the in game info with the current data returned by the in game API,
    # returns None only of the request was not made because of an error
    async def create_in_game_info(self, response):
        in_game_info = InGameInfo()

        in_game_info.in_game = response != None
        if not response:
            return in_game_info
        in_game_info.game_id = response['gameId']
        in_game_info.game_length_minutes = round(
            response['gameLength'] / 60)
        # Assign team ids, there should be only two possible values
        team_ids = list(set([participant['teamId']
                        for participant in response['participants']]))
        if len(team_ids) != 2:
            logger.error('Riot has not provided exactly two team ids')
            return None
        # Fill in both of the teams
        in_game_info.teams.append([])
        in_game_info.teams.append([])
        for participant in response['participants']:
            if participant['teamId'] == team_ids[0]:
                in_game_info.teams[0].append(await self.create_participant(participant))
            elif participant['teamId'] == team_ids[1]:
                in_game_info.teams[1].append(await self.create_participant(participant))
            else:
                logger.error('Participant does not belong to any team')
                return None
        return in_game_info

    # Creates a participant from the in game participant data. This function
    # may make additional requests
    async def create_participant(self, response):
        if not response:
            return None
        participant = Participant()
        participant.player_name = response['summonerName']
        participant.player_id = response['summonerId']
        # Champion name and spell names
        champion_id = response['championId']
        participant.champion_name = await self.get_champion_name(champion_id)
        if participant.champion_name == None:
            return None
        participant.spell1_name = await self.get_spell_name(response['spell1Id'])
        if participant.spell1_name == None:
            return None
        participant.spell2_name = await self.get_spell_name(response['spell2Id'])
        if participant.spell2_name == None:
            return None
        participant.mastery = await self.get_mastery_info(participant.player_id, champion_id)
        if participant.mastery == None:
            return None
        return participant

    # Creates the internal data for champions
    async def request_champion_data(self):
        # Build the request
        url = self.route_champions

        # Make the request and check everything is OK
        response = await self._get(url, {})
        if response.status_code != 200:
            logger.error('Could not make request to Riot champions API')
            return None

        # Keep a copy of the data
        for champion in response.data['data'].values():
            self.data_champions[int(champion['key'])] = champion['id']
        self.database.set_champions(self.data_champions)

    # Creates the internal data for spells
    async def request_spell_data(self):
        # Build the request
        url = self.route_spells

        # Make the request and check everything is OK
        response = await self._get(url, {})
        if response.status_code != 200:
            logger.error('Could not make request to Riot spells API')
            return None

        # keep a copy of the data
        for spell in response.data['data'].values():
            self.data_spells[int(spell['key'])] = spell['name']
        self.database.set_spells(self.data_spells)

    # Returns the champion name corresponding to a champion id
    async def get_champion_name(self, champion_id):

        if not self.data_champions:
            await self.request_champion_data()

        if not champion_id in self.data_champions:
            logger.error(f'Could not find name of champion id {champion_id}')
            return None
        return self.data_champions[champion_id]

    # Returns the name of a spell given its id
    async def get_spell_name(self, spell_id):

        if not self.data_spells:
            await self.request_spell_data()

        if not spell_id in self.data_spells:
            logger.error(f'Could not find name of spell id {spell_id}')
            return None
        return self.data_spells[spell_id]

    # The bot sends the database once initialised. Take the time here to
    # see if the database already has useful information for us
    def set_database(self, database):
        self.database = database
        self.data_champions = self.database.get_champions()
        self.data_spells = self.database.get_spells()
        self.names = self.database.get_names()

    # Returns the player id of the provided player name
    async def get_player_id(self, player_name):

        # First check if we already have an id for this player
        for player_id in self.names:
            if self.names[player_id] == player_name:
                return player_id

        # Build the request
        url = self.riot_schema + self.route_summoner + player_name
        header = self.build_api_header()
        if header == None:
            logger.error('Could not build the request header')
            return None

        # Make the request to the server and check the response
        response = await self._get(url, header=header)
        if response.status_code != 200:
            logger.error('Could not make request to the Riot summoner API')
            return None

        if not response.data:
            logger.info(f'Player {player_name} not found')
            return None

        # Keep a copy of the player id for later
        player_id = response.data['id']
        if player_id in self.names:
            # In this case, we have an alternative name for the player, so nothing to do
            logger.debug(
                f'Player with id {player_id} already exists in the database with another name')
        else:
            logger.debug(
                f'Caching player {player_name} with player id {player_id}')
            self.names[player_id] = player_name
            self.database.add_name(player_id, player_name)
        return player_id

    # Returns the player name provided the id. In principle, only names for players
    # which have already been registered will be requested, so they must be found in memory
    def get_player_name(self, player_id):
        if player_id in self.names:
            return self.names[player_id]
        else:
            logger.error(f'Player name not found for id {player_id}')
            return None

    # Purges the current content of player names by taking into account
    # the list of ids to keep
    def purge_names(self, ids_to_keep):
        logger.info(f'Current number of names: {len(self.names)}')
        logger.info(f'Names to keep: {len(ids_to_keep)}')
        # First purge the data in memory
        for id in [id for id in self.names]:
            if not id in ids_to_keep:
                self.names.pop(id)
        # Now that the final dictionary is built, call the database to also perform the purge
        self.database.keep_names(ids_to_keep)

    # Returns a header that includes the API key.
    # Returns None of the header could not be built.
    def build_api_header(self):
        if self.api_key == None:
            logger.error('API key is not available')
            return None
        return {'X-Riot-Token': self.api_key}

    # Makes a simple request using the requests module.
    async def _get(self, url, header):

        # Wait until the request can be made
        vital = not self.route_active_games in url
        allowed = await self.rate_limiter.allowed(vital)
        if not allowed:
            logger.warning('Rate limiter is not allowing the request')
            return Response(None)
        logger.debug(f'Making a request to url {url}')

        # Make the request and check the connection was good
        return Response(requests.get(url, headers=header))
