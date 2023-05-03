import riotapi
import asyncio
import parsing
import math


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
        # Bot prefix being used in this server
        self.prefix = 'chanclol'

    # Register a new player in the internal list
    async def register(self, riot_api, player_name):

        # Check if the player is already in the list
        if player_name in self.players:
            response = f'Player {player_name} is already registered'
            print(response)
            await self.channel.send(response)
            return

        # Check the player in fact exists
        league_info = riot_api.get_league_info(player_name)
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

    # Changes the prefix in this server
    async def change_prefix(self, new_prefix):
        self.prefix = new_prefix
        response = f'Prefix has been changed to {self.prefix}'
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
        parsed_input = parsing.Parser(message.content, guild.prefix)
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
            elif parsed_input.command == parsing.Command.PREFIX:
                await guild.change_prefix(parsed_input.arguments[0])
            else:
                raise ValueError('Command is not one of the possible ones')

    async def loop_check_games(self):
        while True:
            for guildid in self.guilds:
                for player in self.guilds[guildid].players.values():
                    # Make a request to Riot and check if the player is in game
                    active_game_info = self.riot_api.get_active_game_info(
                        player.name)
                    if active_game_info == None:
                        print(
                            f'Error retrieving in-game data for player {player.name}')
                    elif not active_game_info.in_game:
                        print(f'Player {player.name} is currently not in game')
                    else:
                        response = f'Player {player.name} is in game'
                        print(response)
                        if player.last_informed_game_id != active_game_info.game_id:
                            response += '\n' + \
                                self.create_in_game_message(active_game_info)
                            asyncio.create_task(
                                self.guilds[guildid].channel.send(response))
                            player.last_informed_game_id = active_game_info.game_id
                        else:
                            print(
                                f'In game message for player {player.name} has already been sent')

            await asyncio.sleep(10)

    def create_in_game_message(self, active_game_info):
        message = f'Time elapsed: {math.floor(active_game_info.game_length / 60)} minutes\n'
        team_counter = 1
        for team in [active_game_info.team_1, active_game_info.team_2]:
            message += self.create_in_game_team_message(team, team_counter)
            team_counter += 1
        return message

    def create_in_game_team_message(self, team, number):
        message = f'Team {number}:\n'
        for participant in team:
            message += f' * Champion: {participant.champion_name}, Player: {participant.player_name}, '
            message += f'Mastery: {participant.mastery.level}\n'
            message += f'   Days without playing this champion: {participant.mastery.days_since_last_played}\n'
            message += f'   Spell 1: {participant.spell1_name}, Spell 2: {participant.spell2_name}\n'
        return message
