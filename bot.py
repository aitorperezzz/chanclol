import riotapi
import asyncio
import parsing
import discord


class Player:
    # A player registered inside a guild

    def __init__(self, name):
        # Name of the player (Riot account username)
        self.name = name
        # The id of the last game that was informed for this user
        self.last_informed_game_id = None


class Guild:
    # Any guild where this bot has been invited

    def __init__(self, id, channel_id):
        # Unique identifier of the guild as handled by discord
        self.id = id
        # Id of the channel where the bot will send in-game messages
        self.channel_id = channel_id
        # List of players registered in this guild
        self.players = {}

    # Register a new player in the internal list
    async def register(self, player_name, riot_api):

        # Check if the player is already in the list
        if player_name in self.players:
            response = f'Player {player_name} is already registered'
            print(response)
            return response

        # Check the player in fact exists
        league_info = await riot_api.get_league_info(player_name, True)
        if league_info == None:
            response = f'Could not get league info from Riot API for player {player_name}'
            print(response)
            return response

        # Now it's safe to add to the list
        self.players[player_name] = Player(player_name)

        # Send a final message
        response = f'Player {player_name} registered correctly'
        print(response)
        response += '\n'
        for league in league_info:
            response += f'Queue {league.queue_type}: rank {league.tier} {league.rank} {league.lps} LPs\n'
        return response

    # Unregister a player from the internal list
    async def unregister(self, player_name):
        # Check if the player is already in the list
        if player_name in self.players:
            del self.players[player_name]
            response = f'Player {player_name} unregistered correctly'
        else:
            response = f'Player {player_name} is not registered'
        print(response)
        return response

    # Print the players currently registered
    async def print(self, bot):
        # Print the players currently registered
        if len(self.players) == 0:
            response = 'No players registered\n'
        else:
            response = f'Players currently registered: {", ".join(self.players.keys())}\n'
        print(response)
        # Print the name of the channel the bot sends messages to
        channel_name = bot.client.get_channel(self.channel_id).name
        if channel_name == None:
            return None
        response += f'Sending messages to channel: {channel_name}'
        return response

    # Change the channel where the in-game messages will be sent to
    async def channel(self, new_channel_name, bot):
        guild = bot.client.get_guild(self.id)
        # First make sure the channel does exist in the guild
        channel = discord.utils.get(guild.channels, name=new_channel_name)
        if channel == None:
            response = f'Channel {new_channel_name} does not exist in this server'
        else:
            response = f'From now on, I will send messages to channel {new_channel_name}'
            self.channel_id = channel.id
        print(response)
        return response


class Bot:
    # The bot: receives commands from the discord client
    # and processes them. It runs an infinite loop that checks the
    # in-game status of all the usernames registered for each guild

    def __init__(self, client):
        # All the guild-related information managed by the bot
        self.guilds = {}
        # Riot API class
        self.riot_api = riotapi.RiotApi()
        # Keep a copy of the client
        self.client = client

    # Main entry point for all messages
    async def receive(self, message):
        # Reject my own messages
        if message.author == self.client.user:
            print('Rejecting message sent by myself')
            return

        # For the time being, ignore messages sent on private channels
        if not message.guild:
            print('Ignoring private message')
            await message.channel.send('For the time being, I am ignoring private messages')
            return

        # Register a guild in case it does not yet exist
        if not message.guild.id in self.guilds:
            print(f'initialising guild {message.guild.id}')
            self.guilds[message.guild.id] = Guild(
                message.guild.id, message.channel.id)
            response = f'I will be sending messages to channel {message.channel.name}\n'
            response += 'You can change this anytime by typing "chanclol channel <new_channel_name>"'
            await message.channel.send(response)
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
                response = await guild.register(' '.join(parsed_input.arguments), self.riot_api)
            elif parsed_input.command == parsing.Command.UNREGISTER:
                response = await guild.unregister(' '.join(parsed_input.arguments))
            elif parsed_input.command == parsing.Command.PRINT:
                response = await guild.print(self)
            elif parsed_input.command == parsing.Command.CHANNEL:
                response = await guild.channel(' '.join(parsed_input.arguments), self)
            elif parsed_input.command == parsing.Command.HELP:
                response = self.create_help_message()
            else:
                raise ValueError('Command is not one of the possible ones')
            if response:
                await message.channel.send(response)

    async def loop_check_games(self):
        while True:
            for guildid in list(self.guilds.keys()):
                # If a guild has disappeared while in the process of creating a message, simply continue
                if not guildid in self.guilds:
                    continue
                guild = self.guilds[guildid]
                for player_name in list(guild.players.keys()):
                    # If a player has been unregistered in the process of creating a message, simply continue
                    if not player_name in guild.players:
                        print('Player has been removed from the list')
                        continue
                    # Make a request to Riot to check if the player is in game
                    # We need to forward the game id of the last game that was informed for this user in this guild
                    last_informed_game_id = guild.players[player_name].last_informed_game_id
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
                        guild.players[player_name].last_informed_game_id = active_game_info.game_id
                        # Create the complete response
                        response += '\n' + \
                            self.create_in_game_message(active_game_info)
                        await self.send_message(response, guild.channel_id)

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

    # Send the provided message for the provided channel id, if it exists
    async def send_message(self, message, channel_id):
        # Get the channel from channel id
        channel = self.client.get_channel(channel_id)
        if channel == None:
            print('Could not find channel to send message to')
        else:
            await channel.send(message)

    # Print the response to the help command
    def create_help_message(self):
        message = 'Commands supported:\n'
        message += 'chanclol register <player_name>: register a new player\n'
        message += 'chanclol unregister <player_name>: unregister a player previously added\n'
        message += 'chanclol print: print the players currently registered, and the channel the bot is sending messages to\n'
        message += 'chanclol channel <new_channel_name>: change the channel the bot sends messages to\n'
        message += 'chanclol help: print the usage of the different commands'
        return message
