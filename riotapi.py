import requests
import os
import time
from dotenv import load_dotenv
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
        self.team_1 = []
        self.team_2 = []


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
    def __init__(self):
        # Riot schema
        self.riot_schema = 'https://euw1.api.riotgames.com'
        # Variable that will hold the API key, can be updated on the fly
        self.api_key = None
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
        # Internal copy of encrypted summoner ids to prevent too many requests
        self.encrypted_summoner_ids = {}
        # Create a rate limiter that will give permissions to make requests to riot API
        # 100 requests in 2 minutes
        restriction1 = rate_limiter.Restriction(100, 2 * 60 * 1000)
        # 20 requests per second
        restriction2 = rate_limiter.Restriction(20, 1 * 1000)
        self.rate_limiter = rate_limiter.RateLimiter(
            [restriction1, restriction2])
        # Riot API will have a database (it will be set by the bot)
        self.database = None

    # Returns all the League info for the provided player name.
    # The league info is a list of objects, one for each of the queues for which
    # the player has been placed. If the list is empty, the player is not placed.
    async def get_league_info(self, player_name, cache=False):

        # Get the encrypted summoner id with the player name
        encrypted_summoner_id = await self.get_encrypted_summoner_id(player_name, cache)
        if encrypted_summoner_id == None:
            logger.info(
                f'Could not get encrypted summoner id for player {player_name}')
            return None
        logger.debug('Encrypted summoner id for player {}: {}'.format(
            player_name, encrypted_summoner_id))

        # Build the request
        url = self.riot_schema + self.route_league + encrypted_summoner_id
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

    # Returns the mastery info of certain player with certain champion.
    async def get_mastery_info(self, player_name, champion_id):

        # Get encrypted summoner id
        encrypted_summoner_id = await self.get_encrypted_summoner_id(player_name)
        if encrypted_summoner_id == None:
            logger.error(
                f'Could not get encrypted summoner id for player {player_name}')
            return None

        # Build the request
        url = self.riot_schema + self.route_mastery + encrypted_summoner_id
        url += self.route_mastery_by_champ + str(champion_id)
        header = self.build_api_header()
        if header == None:
            logger.error('Could not build the header for the request')
            return None

        # Make the request and check everything is OK
        response = await self._get(url, header)
        if response.status_code == 404:
            logger.info(
                f'Mastery was not found for this player {player_name} and champion {champion_id} combination')
            return MasteryInfo(None)
        elif response.status_code != 200:
            logger.error(f'Error retrieving mastery for player {player_name}')
            return None
        else:
            return MasteryInfo(response.data)

    # Returns information about ongoing games
    async def get_active_game_info(self, player_name, last_informed_game_id, cache=False):

        # Get encrypted summoner id
        encrypted_summoner_id = await self.get_encrypted_summoner_id(player_name, cache)
        if encrypted_summoner_id == None:
            logger.error(
                f'Could not get encrypted summoner id for player {player_name}')
            return None

        # Build the request
        url = self.riot_schema + self.route_active_games + encrypted_summoner_id
        header = self.build_api_header()
        if header == None:
            logger.error('Could not build the header for the request')
            return None

        # Make the request and check everything is OK
        response = await self._get(url, header)
        if response.status_code == 404:
            logger.debug(f'Player {player_name} is not in game')
            return await self.create_in_game_info(None, None, False)
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
            if last_informed_game_id == game_id:
                # The player has already been informed of this game, so no need to
                # continue with the requests
                logger.debug(
                    f'Player {player_name} is in game and was already informed')
                return await self.create_in_game_info(response.data, True, True)
            else:
                # The player has not yet been informed of this game, so make the complete
                # set of requests
                logger.info(
                    f'Player {player_name} is in game and was never informed')
                return await self.create_in_game_info(response.data, False, True)

    # Creates the in game info with the current data returned by the in game API,
    # and a flag indicating if this game was already informed in the past, in which case,
    # some requests will not be made
    async def create_in_game_info(self, response, previously_informed, in_game):
        in_game_info = InGameInfo()

        in_game_info.in_game = in_game
        if not response:
            return in_game_info
        in_game_info.game_id = response['gameId']
        in_game_info.game_length_minutes = round(
            response['gameLength'] / 60)
        # If the game was already informed in the past, no need to continue
        if previously_informed:
            return in_game_info
        # Assign team ids, there should be only two possible values
        team_ids = list(set([participant['teamId']
                        for participant in response['participants']]))
        if len(team_ids) != 2:
            logger.error('Riot has not provided exactly two team ids')
            return None
        # Fill in both of the teams
        for participant in response['participants']:
            if participant['teamId'] == team_ids[0]:
                in_game_info.team_1.append(await self.create_participant(participant))
            elif participant['teamId'] == team_ids[1]:
                in_game_info.team_2.append(await self.create_participant(participant))
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
        # To get the champion name, I need to make a request
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
        participant.mastery = await self.get_mastery_info(participant.player_name, champion_id)
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
        self.encrypted_summoner_ids = self.database.get_encrypted_summoner_ids()

    # Returns the encrypted summoner id provided the player name.
    async def get_encrypted_summoner_id(self, player_name, cache=False):

        # First check if we already have a copy of this value, to avoid
        # executing too many requests
        if player_name in self.encrypted_summoner_ids:
            return self.encrypted_summoner_ids[player_name]

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

        # Keep a copy of the encrypted summoner id for later, in case the data
        # is requested to be cached
        if not response.data:
            logger.info(f'Player {player_name} not found')
            return None
        encrypted_summoner_id = response.data['id']
        if cache:
            self.encrypted_summoner_ids[player_name] = encrypted_summoner_id
            self.database.add_encrypted_summoner_id(
                player_name, encrypted_summoner_id)
        return encrypted_summoner_id

    # Returns a header that includes the API key.
    # Returns None of the header could not be built.
    def build_api_header(self):
        api_key = self.get_api_key()
        if api_key == None:
            logger.error('Could not get the Riot API key')
            return None
        return {'X-Riot-Token': api_key}

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

    # Returns the API key as found in the environment
    def get_api_key(self):
        load_dotenv()
        if self.api_key != None:
            return self.api_key
        else:
            self.api_key = os.getenv('RIOT_API_KEY')
            if self.api_key == None:
                logger.error(
                    'RIOT_API_KEY has not been found in the environment')
            return self.api_key
