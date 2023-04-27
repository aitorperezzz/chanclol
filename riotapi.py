import requests
import os
from dotenv import load_dotenv


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
        # Dragon route to fetch info about the champions
        self.route_champions = 'http://ddragon.leagueoflegends.com/cdn/10.20.1/data/en_US/champion.json'

    # Returns all the League info for the provided player name.
    # The league info is a list of dicts, one for each of the queues for which
    # the user has been placed. If the list is empty, the user is not placed.
    # Returns None if error.
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
        if response == None:
            print('ERROR making a request to the Riot league API')
            return None

        print(response)
        return response

    # Returns the mastery info of certain player with certain champion.
    # Returns None if error.
    def get_mastery_info(self, player_name, champion_name):

        # Get encrypted summoner ID
        encrypted_summoner_id = self.get_encrypted_summoner_id(player_name)
        if encrypted_summoner_id == None:
            print('ERROR: could not get encrypted summoner ID')
            return None

        # Get champion ID
        champion_id = self.get_champion_id(champion_name)
        if champion_id == None:
            print('ERROR: could not get champion ID')
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
        if response == None:
            print('ERROR making a request to the Riot mastery API')
            return None

        return response

    # Returns the champion ID (an integer) provided the champion name.
    # Returns None if error
    def get_champion_id(self, champion_name):

        # Build the request
        url = self.route_champions

        # Make the request and check everything is OK
        response = self._get(url, {})
        if response == None:
            print('ERROR: could not make request to Riot champions API')
            return None

        # Extract the value we need
        try:
            return response['data'][champion_name]['key']
        except Exception:
            print(
                'ERROR: the response from the Riot champions API is not formatted as expected')
            return None

    # Returns the encrypted summoner id (a string) provided the player name.
    # Returns None if error.
    def get_encrypted_summoner_id(self, player_name):

        # Build the request
        url = self.riot_schema + self.route_summoner + player_name
        header = self.build_api_header()
        if header == None:
            print('ERROR: could not build the request header')
            return None

        # Make the request to the server and check the response
        response = self._get(url, header=header)
        if response == None:
            print('ERROR: could not make request to the Riot summoner API')
            return None

        try:
            return response['id']
        except Exception:
            print(
                'ERROR: the response from the RIOT SUMMONER API is not formatted as expected')
            return None

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
        response = requests.get(url, headers=header)
        if response == None:
            print('ERROR establishing connection')
            return None

        if response.status_code != 200:
            print('ERROR making the request to the Riot API, status code is not 200')
            return None

        return response.json()

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
