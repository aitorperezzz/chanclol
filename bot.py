import riotapi
import asyncio
import parsing
import discord
import message_formatter
import database


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
    async def register(self, player_name, riot_api, database):

        # Check if the player is already in the list
        if player_name in self.players:
            print(f'Player {player_name} is already registered')
            return message_formatter.player_already_registered(player_name)

        # Check the player in fact exists
        league_info = await riot_api.get_league_info(player_name, True)
        if league_info == None:
            print(
                f'Could not get league info from Riot API for player {player_name}')
            return message_formatter.no_response_league_api(player_name)

        # Now it's safe to add the new player
        self.players[player_name] = Player(player_name)
        database.add_player_to_guild(self.id, player_name)

        # Send a final message
        print(f'Player {player_name} registered correctly')
        return message_formatter.player_registered(player_name, league_info)

    # Unregister a player from the internal list
    async def unregister(self, player_name, database):
        # Check if the player is already in the list
        if player_name in self.players:
            del self.players[player_name]
            print(f'Player {player_name} unregistered correctly')
            database.remove_player_from_guild(self.id, player_name)
            return message_formatter.player_unregistered_correctly(player_name)
        else:
            print(f'Player {player_name} was not registered previously')
            return message_formatter.player_not_previously_registered(player_name)

    # Print the players currently registered
    async def print(self, bot):
        channel_name = bot.client.get_channel(self.channel_id).name
        if channel_name == None:
            raise ValueError(
                'Internal channel id has not been found for this guild')
        return message_formatter.print(self.players, channel_name)

    # Change the channel where the in-game messages will be sent to
    async def channel(self, new_channel_name, bot, database):
        guild = bot.client.get_guild(self.id)
        # First make sure the channel does exist in the guild
        channel = discord.utils.get(guild.channels, name=new_channel_name)
        if channel == None:
            print(f'Channel {new_channel_name} does not exist')
            return message_formatter.channel_does_not_exist(new_channel_name)
        else:
            self.channel_id = channel.id
            database.set_channel_id(self.id, self.channel_id)
            print(f'Channel changed to {new_channel_name}')
            return message_formatter.channel_changed(new_channel_name)


class Bot:
    # The bot: receives commands from the discord client
    # and processes them. It runs an infinite loop that checks the
    # in-game status of all the usernames registered for each guild

    def __init__(self, client):
        # Riot API class
        self.riot_api = riotapi.RiotApi()
        # Keep a copy of the client
        self.client = client
        # Create the database
        self.database = database.Database()
        # Initialise the riot API with possible contents inside the database
        self.riot_api.set_database(self.database)
        # All the guild-related information managed by the bot
        self.guilds = self.database.get_guilds()

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
            print(f'Initialising guild {message.guild.id}')
            self.guilds[message.guild.id] = Guild(
                message.guild.id, message.channel.id)
            self.database.add_guild(message.guild.id, message.channel.id)
            response = message_formatter.welcome(message.channel.name)
            await message.channel.send(content=response.content, embed=response.embed)
        guild = self.guilds[message.guild.id]

        # Parse the input provided and call the appropriate function
        parsed_input = parsing.Parser(message.content)
        if parsed_input.code == parsing.ParseResult.NOT_BOT_PREFIX:
            print('Rejecting message not intended for the bot')
        elif parsed_input.code != parsing.ParseResult.OK:
            syntax_error_string = parsed_input.get_error_string()
            print(f'Input not valid: {syntax_error_string}')
            response = message_formatter.input_not_valid(syntax_error_string)
            await message.channel.send(content=response.content, embed=response.embed)
        else:
            print('Command understood')
            if parsed_input.command == parsing.Command.REGISTER:
                response = await guild.register(' '.join(parsed_input.arguments), self.riot_api, self.database)
            elif parsed_input.command == parsing.Command.UNREGISTER:
                response = await guild.unregister(' '.join(parsed_input.arguments), self.database)
            elif parsed_input.command == parsing.Command.PRINT:
                response = await guild.print(self)
            elif parsed_input.command == parsing.Command.CHANNEL:
                response = await guild.channel(' '.join(parsed_input.arguments), self, self.database)
            elif parsed_input.command == parsing.Command.HELP:
                response = message_formatter.create_help_message()
            else:
                raise ValueError('Command is not one of the possible ones')
            if response:
                await message.channel.send(content=response.content, embed=response.embed)

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
                        print('Player has been removed from the list while iterating')
                        continue
                    # Make a request to Riot to check if the player is in game
                    # We need to forward the game id of the last game that was informed for this user in this guild
                    last_informed_game_id = guild.players[player_name].last_informed_game_id
                    active_game_info = await self.riot_api.get_active_game_info(
                        player_name, last_informed_game_id, cache=True)
                    if active_game_info == None:
                        print(
                            f'In-game data for player {player_name} is not available')
                    elif not active_game_info.in_game:
                        print(f'Player {player_name} is currently not in game')
                    elif last_informed_game_id == active_game_info.game_id:
                        print(
                            f'Message for player {player_name} for this game was already sent')
                    else:
                        print(
                            f'Player {player_name} is in game and a message has to be sent')
                        # Update the last informed game_id
                        guild.players[player_name].last_informed_game_id = active_game_info.game_id
                        self.database.set_last_informed_game_id(
                            player_name, guild.id, active_game_info.game_id)
                        # Create the complete response
                        message = message_formatter.in_game_message(
                            active_game_info, player_name)
                        await self.send_message(message, guild.channel_id)

            await asyncio.sleep(10)

    # Send the provided message for the provided channel id, if it exists
    async def send_message(self, message, channel_id):
        # Get the channel from channel id
        channel = self.client.get_channel(channel_id)
        if channel == None:
            print('Could not find channel to send message to')
        else:
            await channel.send(content=message.content, embed=message.embed)
