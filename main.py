import riotapi

def main():

	# Select the name of the player we want to get info about.
	playerName = 'SrEgea1'

	# Get general League info about this player.
	leagueInfo = riotapi.getLeagueInfo(playerName)
	print(leagueInfo)

	# Get mastery info of this player with a specific champion.
	championName = 'Thresh'
	masteryInfo = riotapi.getMasteryInfo(playerName, championName)
	print(masteryInfo)

if __name__ == '__main__':
	main()