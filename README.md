# lol-stats-bot
Discord bot written in Python to retrieve info before a League of Legends game starts.

Just after a League of Legends game starts, call this bot with the command `chanclas` to tell you information about the players in your current game. For each player, you will be able to fetch:
- The name of the player.
- The champion he or she is playing during the current game.
- The mastery of the player with the current champion.
- The rank of the player and the LPs.
- The global winrate percentage of the player in the current season.

## Dependencies
The code is written in python 3 and makes use of:
- The `requests` module that helps us make requests to the Riot API. It can be downloaded from [pypi](https://pypi.org/project/requests/).
- The `discord.py` module that provides a high level access to the Discord API, which can be also downloaded at [pypi](https://pypi.org/project/discord.py/).
