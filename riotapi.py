import requests
import os
import time
import asyncio
from dotenv import load_dotenv


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
        if response == None:
            return None
        # A copy of the status code will always be kept
        self.status_code = response.status_code
        if self.status_code == 200:
            # This is the only case where there is a response
            self.data = response.json()
        elif self.status_code == 429:
            print('Rate limit exceeded')
        elif self.status_code == 404:
            print('Data not found')
        else:
            print(f'Error connecting to Riot API: {response.json()}')


class RateLimiter:
    # Class that will tell the caller if a certain call can be done or not. It keeps
    # an internal count of the time and only returns OK when sufficient time has elapsed

    def __init__(self, seconds_between_requests):
        self.seconds_between_requests = seconds_between_requests
        self.time = time.time()

    # Returns true if a request can be made at this moment. Additionally, after accepting
    # a request it will udpate its internal timer of the last request
    def can_perform_request(self):
        current_time = time.time()
        make_request = current_time - self.time > self.seconds_between_requests
        if make_request:
            self.time = time.time()
        return make_request


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
        # Create a rate limiter, which will answer if a request can be done or not
        self.rate_limiter = RateLimiter(2)

    # Returns all the League info for the provided player name.
    # The league info is a list of objects, one for each of the queues for which
    # the player has been placed. If the list is empty, the player is not placed.
    async def get_league_info(self, player_name, cache=False):

        # Get the encrypted summoner id with the player name
        encrypted_summoner_id = await self.get_encrypted_summoner_id(player_name, cache)
        if encrypted_summoner_id == None:
            print('ERROR: could not get encrypted summoner ID')
            return None
        print('Encrypted summoner ID for {}: {}'.format(
            player_name, encrypted_summoner_id))

        # Build the request
        url = self.riot_schema + self.route_league + encrypted_summoner_id
        header = self.build_api_header()
        if header == None:
            print('ERROR: could not build the header for the request')
            return None

        # Make the request to the server
        response = await self._get(url, header)
        if response == None or response.status_code != 200:
            print('ERROR making a request to the Riot league API')
            return None

        # Prepare the final result
        result = []
        for league in response.data:
            result.append(LeagueInfo(league))
        return result

    # Returns the mastery info of certain player with certain champion.
    async def get_mastery_info(self, player_name, champion_id):

        # Get encrypted summoner ID
        encrypted_summoner_id = await self.get_encrypted_summoner_id(player_name)
        if encrypted_summoner_id == None:
            print('ERROR: could not get encrypted summoner ID')
            return None

        # Build the request
        url = self.riot_schema + self.route_mastery + encrypted_summoner_id
        url += self.route_mastery_by_champ + str(champion_id)
        header = self.build_api_header()
        if header == None:
            print('ERROR: could not build the header for the request')
            return None

        # Make the request and check everything is OK
        response = await self._get(url, header)
        if response == None:
            print('ERROR making a request to the Riot mastery API')
            return None

        return MasteryInfo(response.data if response.status_code == 200 else None)

    # Returns information about ongoing games
    async def get_active_game_info(self, player_name, last_informed_game_id, cache=False):

        # Get encrypted summoner ID
        encrypted_summoner_id = await self.get_encrypted_summoner_id(player_name, cache)
        if encrypted_summoner_id == None:
            print('ERROR: could not get encrypted summoner ID')
            return None

        # Build the request
        url = self.riot_schema + self.route_active_games + encrypted_summoner_id
        header = self.build_api_header()
        if header == None:
            print('ERROR: could not build the header for the request')
            return None

        # Make the request and check everything is OK
        response = await self._get(url, header)
        if response == None:
            print('Error making a request to active game Riot API')
            return None
        elif response.status_code == 404:
            print(f'Player {player_name} is not in game')
            return await self.create_in_game_info(None, None)
        elif response.status_code != 200:
            print('Problem making a request to the Riot active game API')
            return None
        else:
            print(f'Player {player_name} is in game')
            game_id = response.data['gameId']
            if last_informed_game_id == game_id:
                # The player has already been informed of this game, so no need to
                # continue with the requests
                print(f'Player {player_name} was already informed')
                return await self.create_in_game_info(response.data, True)
            else:
                # The player has not yet been informed of this game, so make the complete
                # set of requests
                print(f'Player {player_name} was never informed')
                return await self.create_in_game_info(response.data, False)

    # Creates the in game info with the current data returned by the in game API,
    # and a flag indicating if this game was already informed in the past, in which case,
    # some requests will not be made
    async def create_in_game_info(self, response, previously_informed):
        in_game_info = InGameInfo()

        # If no response, it means the player is not playing
        in_game_info.in_game = True if response else False
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
            print('Riot has not provided exactly two team ids')
            return None
        # Fill in both of the teams
        for participant in response['participants']:
            if participant['teamId'] == team_ids[0]:
                in_game_info.team_1.append(await self.create_participant(participant))
            elif participant['teamId'] == team_ids[1]:
                in_game_info.team_2.append(await self.create_participant(participant))
            else:
                print('Participant does not belong to any team')
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
        if response == None:
            print('ERROR: could not make request to Riot champions API')
            return None

        # keep a copy of the data
        self.data_champions = response.data['data']

    # Creates the internal data for spells
    async def request_spell_data(self):
        # Build the request
        url = self.route_spells

        # Make the request and check everything is OK
        response = await self._get(url, {})
        if response == None:
            print('ERROR: could not make request to Riot spells API')
            return None

        # keep a copy of the data
        self.data_spells = response.data['data']

    # Returns the champion ID provided the champion name.
    async def get_champion_id(self, champion_name):

        if not self.data_champions:
            await self.request_champion_data()

        # Extract the value we need
        return self.data_champions[champion_name]['key']

    # Returns the champion name corresponding to a champion id
    async def get_champion_name(self, champion_id):

        if not self.data_champions:
            await self.request_champion_data()

        # Loop over all the champions and look for the one we want
        for champion in self.data_champions.values():
            if int(champion['key']) == champion_id:
                return champion['id']
        # At this point the champion has not been found
        print(f'Could not find name of champion id {champion_id}')
        return None

    # Returns the name of a spell given its id
    async def get_spell_name(self, spell_id):

        if not self.data_spells:
            await self.request_spell_data()

        # Loop over all the spells and look for the one we want
        for spell in self.data_spells.values():
            if int(spell['key']) == spell_id:
                return spell['name']
        # At this point the spell has not been found
        print(f'Could not find name of spell id {spell_id}')
        return None

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
            print('ERROR: could not build the request header')
            return None

        # Make the request to the server and check the response
        response = await self._get(url, header=header)
        if response == None:
            print('ERROR: could not make request to the Riot summoner API')
            return None

        # Keep a copy of the encrypted summoner id for later, in case the data
        # is requested to be cached
        encrypted_summoner_id = response.data['id']
        if cache:
            self.encrypted_summoner_ids[player_name] = encrypted_summoner_id
        return encrypted_summoner_id

    # Returns a header that includes the API key.
    # Returns None of the header could not be built.
    def build_api_header(self):
        api_key = self.get_api_key()
        if api_key == None:
            print('Could not get the Riot API key')
            return None
        return {'X-Riot-Token': api_key}

    # Makes a simple request using the requests module.
    async def _get(self, url, header):

        # Wait until the request can be made
        while not self.rate_limiter.can_perform_request():
            print(' *** Waiting to make request...')
            await asyncio.sleep(self.rate_limiter.seconds_between_requests)
        print(f' *** Making a request to url {url}')

        # Make the request and check the connection was good
        response = requests.get(url, headers=header)
        if response == None:
            print(' *** ERROR establishing connection')
            return None

        return Response(response)

    # Returns the API key as found in the environment
    def get_api_key(self):
        load_dotenv()
        if self.api_key != None:
            return self.api_key
        else:
            self.api_key = os.getenv('RIOT_API_KEY')
            if self.api_key == None:
                print('RIOT_API_KEY has not been found in the environment')
            return self.api_key
