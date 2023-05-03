import requests
import os
import time
import math
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

    def __init__(self, participant, riotapi):
        if not participant:
            return None
        self.player_name = participant['summonerName']
        # To get the champion name, I need to make a request
        champion_id = participant['championId']
        self.champion_name = riotapi.get_champion_name(champion_id)
        if self.champion_name == None:
            return None
        self.spell1_name = riotapi.get_spell_name(participant['spell1Id'])
        if self.spell1_name == None:
            return None
        self.spell2_name = riotapi.get_spell_name(participant['spell2Id'])
        if self.spell2_name == None:
            return None
        self.mastery = riotapi.get_mastery_info(self.player_name, champion_id)
        if self.mastery == None:
            return None


class InGameInfo:
    # Information about an on going game

    def __init__(self, response, riot_api):
        # If no response, it means the player is not playing
        self.in_game = True if response else False
        if not response:
            return
        self.game_id = response['gameId']
        self.game_length = response['gameLength']
        # If no Riot API, it means the game was already informed in the past, so
        # no need to continue to fill in data
        if not riot_api:
            return
        # Assign team ids, there should be only two possible values
        team_ids = list(set([participant['teamId']
                        for participant in response['participants']]))
        if len(team_ids) != 2:
            print('Riot has not provided exactly two team ids')
            return None
        # Fill in both of the teams
        self.team_1 = []
        self.team_2 = []
        for participant in response['participants']:
            if participant['teamId'] == team_ids[0]:
                self.team_1.append(Participant(participant, riot_api))
            elif participant['teamId'] == team_ids[1]:
                self.team_2.append(Participant(participant, riot_api))
            else:
                print('Participant does not belong to any team')
                return None


class MasteryInfo:
    # Information about how good is a player with a certain champion

    def __init__(self, response):
        if not response:
            return None
        # Mastery level
        self.level = response['championLevel']
        # lastPlayTime is in Unix milliseconds
        time_in_seconds = time.time()
        self.days_since_last_played = math.floor((time_in_seconds -
                                                  response['lastPlayTime'] / 1000) / 3600 / 24)


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
        # Last informed game id for each of the players for which a game has been informed
        self.informed_game_ids = {}

    # Returns all the League info for the provided player name.
    # The league info is a list of objects, one for each of the queues for which
    # the user has been placed. If the list is empty, the user is not placed.
    def get_league_info(self, player_name):

        # Get the encrypted summoner id with the username
        encrypted_summoner_id = self.get_encrypted_summoner_id(player_name)
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
        response = self._get(url, header)
        if response['response'] == None:
            print('ERROR making a request to the Riot league API')
            return None

        # Prepare the final result
        result = []
        for league in response['response']:
            result.append(LeagueInfo(league))
        return result

    # Returns the mastery info of certain player with certain champion.
    def get_mastery_info(self, player_name, champion_id):

        # Get encrypted summoner ID
        encrypted_summoner_id = self.get_encrypted_summoner_id(player_name)
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
        response = self._get(url, header)
        if response['response'] == None:
            print('ERROR making a request to the Riot mastery API')
            return None

        return MasteryInfo(response['response'])

    # Returns information about ongoing games
    def get_active_game_info(self, player_name):

        # Get encrypted summoner ID
        encrypted_summoner_id = self.get_encrypted_summoner_id(player_name)
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
        response = self._get(url, header)
        if response['status_code'] == None:
            print('Connection error')
            return None
        elif response['status_code'] == 404:
            print('User is not in game')
            return InGameInfo(None, None)
        elif response['status_code'] != 200:
            print('Problem making a request to the Riot active game API')
            return None
        else:
            print('User is in game')
            game_id = response['response']['gameId']
            if not player_name in self.informed_game_ids:
                # The player is currently playing and was never informed on any game,
                # so a complete response needs to be built,
                # and the game id added as the last one informed
                self.informed_game_ids[player_name] = game_id
                return InGameInfo(response['response'], self)
            elif self.informed_game_ids[player_name] == game_id:
                # The player is playing, but this game was already informed
                return InGameInfo(response['response'], None)
            else:
                # The player was informed previously for another game, so the internal list
                # needs to get updated with the new game id, and a complete response built
                self.informed_game_ids[player_name] = game_id
                return InGameInfo(response['response'], self)

    # Creates the internal data for champions
    def request_champion_data(self):
        # Build the request
        url = self.route_champions

        # Make the request and check everything is OK
        response = self._get(url, {})
        if response['response'] == None:
            print('ERROR: could not make request to Riot champions API')
            return None

        # keep a copy of the data
        self.data_champions = response['response']['data']

    # Creates the internal data for spells
    def request_spell_data(self):
        # Build the request
        url = self.route_spells

        # Make the request and check everything is OK
        response = self._get(url, {})
        if response['response'] == None:
            print('ERROR: could not make request to Riot spells API')
            return None

        # keep a copy of the data
        self.data_spells = response['response']['data']

    # Returns the champion ID provided the champion name.
    def get_champion_id(self, champion_name):

        if not self.data_champions:
            self.request_champion_data()

        # Extract the value we need
        return self.data_champions[champion_name]['key']

    # Returns the champion name corresponding to a champion id
    def get_champion_name(self, champion_id):

        if not self.data_champions:
            self.request_champion_data()

        # Loop over all the champions and look for the one we want
        for champion in self.data_champions.values():
            if int(champion['key']) == champion_id:
                return champion['id']
        # At this point the champion has not been found
        print(f'Could not find name of champion id {champion_id}')
        return None

    # Returns the name of a spell given its id
    def get_spell_name(self, spell_id):

        if not self.data_spells:
            self.request_spell_data()

        # Loop over all the spells and look for the one we want
        for spell in self.data_spells.values():
            if int(spell['key']) == spell_id:
                return spell['name']
        # At this point the spell has not been found
        print(f'Could not find name of spell id {spell_id}')
        return None

    # Returns the encrypted summoner id provided the player name.
    def get_encrypted_summoner_id(self, player_name):

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
        response = self._get(url, header=header)
        if response['response'] == None:
            print('ERROR: could not make request to the Riot summoner API')
            return None

        # Keep a copy of the encrypted summoner id for later
        encrypted_summoner_id = response['response']['id']
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
    def _get(self, url, header):
        return_value = {'status_code': None, 'response': None}
        print(f' *** Making a request to url {url}')

        # Make the request and check the connection was good
        response = requests.get(url, headers=header)
        if response == None:
            print('ERROR establishing connection')
            return return_value

        # Decide depending on the status code
        return_value['status_code'] = response.status_code
        if response.status_code != 200:
            print('Error processing request to Riot API')
            print(response)
        else:
            return_value['response'] = response.json()
        return return_value

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
