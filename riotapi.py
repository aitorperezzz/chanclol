import requests

# Define the RIOT schema.
RIOT_SCHEMA = 'https://euw1.api.riotgames.com'

# Define the filename of the API key.
APIKEY_FILENAME = 'apikey.txt'

# Define the routes inside the Riot API.
ROUTE_SUMMONER = '/lol/summoner/v4/summoners/by-name/'
ROUTE_LEAGUE = '/lol/league/v4/entries/by-summoner/'
ROUTE_MASTERY = '/lol/champion-mastery/v4/champion-masteries/by-summoner/'
ROUTE_MASTERY_BY_CHAMP = '/by-champion/'

# Define the Dragon route to fetch info about the champions.
ROUTE_CHAMPIONS = 'http://ddragon.leagueoflegends.com/cdn/10.20.1/data/en_US/champion.json'


# Returns all the League info for the provided player name.
# Returns None if some error occurred.
def getLeagueInfo(playerName):

	# Get the encrypted summoner id from the player name.
	encryptedSummonerId = _getEncryptedSummonerId(playerName)
	if encryptedSummonerId == None:
		print('ERROR: could not get encrypted summoner ID')
		return None
	print('Encrypted summoner ID for {}: {}'.format(playerName, encryptedSummonerId))

	# Build the request.
	url = RIOT_SCHEMA + ROUTE_LEAGUE + encryptedSummonerId
	header = _buildAPIHeader()
	if header == None:
		print('ERROR: could not build the header for the request')
		return None

	# Make the request to the server.
	response = _get(url, header)
	if response == None:
		print('ERROR making a request to the LEAGUE RIOT API')
		return None

	return response.json()


# Returns the mastery info of certain player with certain champion.
# Returns None if error.
def getMasteryInfo(playerName, championName):

	# Get encrypted summoner ID.
	encryptedSummonerId = _getEncryptedSummonerId(playerName)
	if encryptedSummonerId == None:
		print('ERROR: could not get encrypted summoner ID')
		return None

	# Get champion ID.
	championId = _getChampionId(championName)
	if championId == None:
		print('ERROR: could not get champion ID')
		return None

	# Build the request.
	url = RIOT_SCHEMA + ROUTE_MASTERY + encryptedSummonerId
	url += ROUTE_MASTERY_BY_CHAMP + str(championId)
	header = _buildAPIHeader()
	if header == None:
		print('ERROR: could not build the header for the request')
		return None

	# Make the request and check everything is OK.
	response = _get(url, header)
	if response == None:
		print('ERROR making a request to the RIOT MASTERY API')
		return None

	return response.json()


# Returns the champion ID (an integer) provided the champion name.
def _getChampionId(championName):

	# Build the request.
	url = ROUTE_CHAMPIONS

	# Make the request and check everything is OK.
	response = _get(url, {})
	if response == None:
		print('ERROR: could not make request to RIOT CHAMPIONS API')
		return None

	# Extract the value we need
	try:
		return response.json()['data'][championName]['key']
	except Exception:
		print ('ERROR: the response from the RIOT CHAMPIONS API is not formatted as expected')
		return None


# Returns the encrypted summoner id (a string) provided the player name.
def _getEncryptedSummonerId(playerName):

	# Build the request.
	url = RIOT_SCHEMA + ROUTE_SUMMONER + playerName
	header = _buildAPIHeader()
	if header == None:
		print('ERROR: could not build the request header')
		return None

	# Make the request to the server and check the response.
	response = _get(url, header=header)
	if response == None:
		print('ERROR: could not make request to the SUMMONER RIOT API')
		return None

	try:
		return response.json()['id']
	except Exception:
		print('ERROR: the response from the RIOT SUMMONER API is not formatted as expected')
		return None


# Returns a header that includes the API key.
def _buildAPIHeader():
	# Get the API key from the external file.
	apiKey = _loadAPIKeyFromFile()
	if apiKey == None:
		print('ERROR: could not extract API key from file')
		return None

	return {'X-Riot-Token': apiKey}


# Makes a simple request using the requests module.
def _get(url, header):
	response = requests.get(url, headers=header)
	if response == None:
		print('ERROR establishing connection')
		return None

	if response.status_code != 200:
		print('ERROR making the request to the RIOT API, status code is not 200')
		return None

	return response.json()


# Returns the API key string stored inside the file (as a string).
def _loadAPIKeyFromFile():
	try:
		with open(APIKEY_FILENAME, 'r') as apikeyFile:
			return apikeyFile.read()
	except Exception:
		print('ERROR: API key file could not be opened')
		print(Exception)
		return None
