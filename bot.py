import riotapi
import asyncio
import parsing


class Player:
    # A player registered inside a guild

    def __init__(self, name):
        # Name of the player (Riot account username)
        self.name = name
        # The id of the last game that was informed for this user
        self.last_informed_game_id = None


class Guild:
    # Any guild where this bot has been invited

    def __init__(self, id, channel):
        # Unique identifier of the guild as handled by discord
        self.id = id
        # Copy of the channel object to send messages to
        self.channel = channel
        # List of players registered in this guild
        self.players = {}

    # Register a new player in the internal list
    async def register(self, riot_api, player_name):

        # Check if the player is already in the list
        if player_name in self.players:
            response = f'Player {player_name} is already registered'
            print(response)
            await self.channel.send(response)
            return

        # Check the player in fact exists
        league_info = await riot_api.get_league_info(player_name, True)
        if league_info == None:
            response = f'Could not get league info from Riot API for player {player_name}'
            print(response)
            await self.channel.send(response)
            return

        # Now it's safe to add to the list
        self.players[player_name] = Player(player_name)

        # Send a final message
        response = f'Player {player_name} registered correctly'
        print(response)
        response += '\n'
        for league in league_info:
            response += f'Queue {league.queue_type}: rank {league.tier} {league.rank} {league.lps} LPs\n'
        await self.channel.send(response)

    # Unregister a player from the internal list
    async def unregister(self, player_name):
        # Check if the player is already in the list
        if player_name in self.players:
            del self.players[player_name]
            response = f'Player {player_name} unregistered correctly'
        else:
            response = f'Player {player_name} is not registered'
        print(response)
        await self.channel.send(response)

    # Print the players currently registered
    async def print(self):
        if len(self.players) == 0:
            response = 'No players registered'
        else:
            response = 'Players currently registered:\n'
            for player_name in self.players:
                response += f'{player_name}\n'
        print(response)
        await self.channel.send(response)


class Bot:
    # The bot: receives commands from the discord client
    # and processes them. It runs an infinite loop that checks the
    # in-game status of all the usernames registered for each guild

    def __init__(self):
        # All the guild-related information managed by the bot
        self.guilds = {}
        # Riot API class
        self.riot_api = riotapi.RiotApi()

    # Main entry point for all messages
    async def receive(self, message, client):
        # Reject my own messages
        if message.author == client.user:
            print('Rejecting message sent by myself')
            return

        # Register a guild in case it does not yet exist
        if not message.guild.id in self.guilds:
            print(f'initialising guild {message.guild.id}')
            self.guilds[message.guild.id] = Guild(
                message.guild.id, message.channel)
        guild = self.guilds[message.guild.id]

        # Parse the input provided and call the appropriate function
        parsed_input = parsing.Parser(message.content)
        if parsed_input.code == parsing.ParseResult.NOT_BOT_PREFIX:
            print('Rejecting message not intended for the bot')
        elif parsed_input.code != parsing.ParseResult.OK:
            response = f'Input is not valid: {parsed_input.get_error_string()}'
            print(response)
            await message.channel.send(response)
        else:
            print('Command understood')
            if parsed_input.command == parsing.Command.REGISTER:
                await guild.register(self.riot_api, ' '.join(parsed_input.arguments))
            elif parsed_input.command == parsing.Command.UNREGISTER:
                await guild.unregister(' '.join(parsed_input.arguments))
            elif parsed_input.command == parsing.Command.PRINT:
                await guild.print()
            else:
                raise ValueError('Command is not one of the possible ones')

    async def loop_check_games(self):
        while True:
            for guildid in list(self.guilds.keys()):
                # If a guild has disappeared while in the process of creating a message, simply continue
                if not guildid in self.guilds:
                    continue
                for player_name in list(self.guilds[guildid].players.keys()):
                    # If a player has been unregistered in the process of creating a message, simply continue
                    if not player_name in self.guilds[guildid].players:
                        print('Player has been removed from the list')
                        continue
                    # Make a request to Riot to check if the player is in game
                    # We need to forward the game id of the last game that was informed for this user in this guild
                    last_informed_game_id = self.guilds[guildid].players[player_name].last_informed_game_id
                    active_game_info = await self.riot_api.get_active_game_info(
                        player_name, last_informed_game_id, cache=True)
                    if active_game_info == None:
                        print(
                            f'Error retrieving in-game data for player {player_name}')
                    elif not active_game_info.in_game:
                        print(f'Player {player_name} is currently not in game')
                    elif last_informed_game_id == active_game_info.game_id:
                        print(
                            f'Message for player {player_name} for this game was already sent')
                    else:
                        response = f'Player {player_name} is in game'
                        print(response)
                        # Update the last informed game_id
                        self.guilds[guildid].players[player_name].last_informed_game_id = active_game_info.game_id
                        response += '\n' + \
                            self.create_in_game_message(active_game_info)
                        await self.guilds[guildid].channel.send(response)

            await asyncio.sleep(10)

    # Build the message that is displayed the first time a player is caught in game
    def create_in_game_message(self, active_game_info):
        message = f'Time elapsed: {active_game_info.game_length_minutes} minutes\n'
        team_counter = 1
        for team in [active_game_info.team_1, active_game_info.team_2]:
            message += self.create_in_game_team_message(team, team_counter)
            team_counter += 1
        return message

    # Create the in-game message for a specific team
    def create_in_game_team_message(self, team, number):
        message = f'Team {number}:\n'
        for participant in team:
            message += f' * Champion: {participant.champion_name}, Player: {participant.player_name}, '
            if participant.mastery.available:
                message += f'Mastery: {participant.mastery.level}\n'
                message += f'   Days without playing this champion: {participant.mastery.days_since_last_played}\n'
            else:
                message += f'Mastery: not available\n'
                message += f'   Days without playing this champion: not available\n'
            message += f'   Spell 1: {participant.spell1_name}, Spell 2: {participant.spell2_name}\n'
        return message
