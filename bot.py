import riotapi
import asyncio
import parsing
import discord
import message_formatter
import database
import logging
import time
import math
import stopwatch

logger = logging.getLogger(__name__)


class Player:
    # A player registered inside a guild

    def __init__(self, name):
        # Name of the player (Riot account username)
        self.name = name
        # The id of the last game that was informed for this user
        self.last_informed_game_id = None
        # Create a stopwatch that will keep track of the last time the in game status was checked
        # for this player
        self.stopwatch = stopwatch.StopWatch(15 * 1000)  # Milliseconds


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
            logger.info(f'Player {player_name} is already registered')
            return message_formatter.player_already_registered(player_name)

        # Check the player in fact exists
        league_info = await riot_api.get_league_info(player_name)
        if league_info == None:
            logger.info(
                f'Could not get league info from Riot API for player {player_name}')
            return message_formatter.no_response_league_api(player_name)

        # Now it's safe to add the new player
        logger.info(f'Registering player {player_name}')
        self.players[player_name] = Player(player_name)
        database.add_player_to_guild(self.id, player_name)

        # Send a final message
        logger.info(f'Player {player_name} has been registered')
        return message_formatter.player_registered(player_name, league_info)

    # Unregister a player from the internal list
    async def unregister(self, player_name, database):
        # Check if the player is already in the list
        if player_name in self.players:
            logger.info(f'Unregistering player {player_name}')
            del self.players[player_name]
            database.remove_player_from_guild(self.id, player_name)
            logger.info(f'Player {player_name} has been unregistered')
            return message_formatter.player_unregistered_correctly(player_name)
        else:
            logger.info(
                f'Cannot unregister player {player_name}: it is not registered')
            return message_formatter.player_not_previously_registered(player_name)

    # Print the players currently registered
    async def print(self, bot):
        channel_name = bot.client.get_channel(self.channel_id).name
        if channel_name == None:
            raise ValueError(
                f'Channel {channel_name} has not been found for this guild')
        return message_formatter.print_config(self.players, channel_name)

    # Change the channel where the in-game messages will be sent to
    async def channel(self, new_channel_name, bot, database):
        guild = bot.client.get_guild(self.id)
        # First make sure the channel does exist in the guild
        channel = discord.utils.get(guild.channels, name=new_channel_name)
        if channel == None:
            logger.info(
                f'Cannot change channel to {new_channel_name} as it does not exist in the server')
            return message_formatter.channel_does_not_exist(new_channel_name)
        else:
            logger.info(
                f'Changing channel to use by this server to {new_channel_name}')
            self.channel_id = channel.id
            database.set_channel_id(self.id, self.channel_id)
            logger.info(f'Channel changed to {new_channel_name}')
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
        # The bot will keep track of the last time the encrypted summoner ids were purged
        # in the database and the riot API
        self.last_purge_encrypted_summoner_ids = time.time()
        self.purge_timeout_hours = 3

    # Main entry point for all messages
    async def receive(self, message):
        # Reject my own messages
        if message.author == self.client.user:
            logger.debug('Rejecting message sent by myself')
            return

        # For the time being, ignore messages sent on private channels
        if not message.guild:
            logger.info('Ignoring private message')
            await message.channel.send('For the time being, I am ignoring private messages')
            return

        # Register a guild in case it does not yet exist
        if not message.guild.id in self.guilds:
            logger.info(f'Initialising guild {message.guild.id}')
            self.guilds[message.guild.id] = Guild(
                message.guild.id, message.channel.id)
            self.database.add_guild(message.guild.id, message.channel.id)
            logger.info('Sending welcome message')
            response = message_formatter.welcome(message.channel.name)
            await message.channel.send(content=response.content, embed=response.embed)
        guild = self.guilds[message.guild.id]

        # Parse the input provided and call the appropriate function
        logger.debug(f'Message received: {message.content}')
        parsed_input = parsing.Parser(message.content)
        if parsed_input.code == parsing.ParseResult.NOT_BOT_PREFIX:
            logger.debug('Rejecting message not intended for the bot')
        elif parsed_input.code != parsing.ParseResult.OK:
            logger.info(f'Wrong input: {message.content}')
            syntax_error_string = parsed_input.get_error_string()
            logger.info(f'Reason: {syntax_error_string}')
            response = message_formatter.input_not_valid(syntax_error_string)
            await message.channel.send(content=response.content, embed=response.embed)
        else:
            logger.info(f'Command understood: {message.content}')
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

    # Get a list of all the guild ids where the player is registered
    def get_guild_ids(self, player_name):
        guild_ids = []
        for guild in self.guilds.values():
            if player_name in guild.players:
                guild_ids.append(guild.id)
        return guild_ids

    # Main loop of the application
    async def loop_check_games(self):
        while True:
            # TODO: investigate if this wait time needs to be updated according to the number of users registered
            await asyncio.sleep(5)
            # Decide if the encrypted summoner ids in the database need to be purged
            self.purge_encrypted_summoner_ids()
            # Find a player to check in this iteration
            player_name = self.select_player_to_check()
            if player_name == None:
                continue
            # We have a player to check
            logger.debug(f'Checking in game status of player {player_name}')
            # Make a request to Riot to check if the player is in game
            active_game_info = await self.riot_api.get_active_game_info(player_name)
            if active_game_info == None:
                logger.warning(
                    f'In-game data for player {player_name} is not available')
                continue
            elif not active_game_info.in_game:
                logger.debug(
                    f'Player {player_name} is currently not in game')
                # TODO: check if the timeout for this player needs to be updated
                continue
            # Player is in game
            # Get the guilds where this player is registered
            guild_ids_player = self.get_guild_ids(player_name)
            for guild_id in guild_ids_player:
                guild = self.guilds[guild_id]
                # Get the last game that was informed for this player in this guild
                last_informed_game_id = guild.players[player_name].last_informed_game_id
                if last_informed_game_id == active_game_info.game_id:
                    logger.debug(
                        f'Message for player {player_name} in guild {guild_id} for this game was already sent')
                else:
                    logger.info(
                        f'Player {player_name} is in game and a message has to be sent to guild {guild_id}')
                    # Update the last informed game_id
                    logger.info('Updating last informed game id')
                    guild.players[player_name].last_informed_game_id = active_game_info.game_id
                    self.database.set_last_informed_game_id(
                        player_name, guild.id, active_game_info.game_id)
                    # Create the complete response
                    message = message_formatter.in_game_message(
                        active_game_info, player_name)
                    await self.send_message(message, guild.channel_id)

    # Send the provided message for the provided channel id, if it exists
    async def send_message(self, message, channel_id):
        # Get the channel from channel id
        channel = self.client.get_channel(channel_id)
        if channel == None:
            logger.error(
                f'Could not find channel {channel_id} to send message to')
        else:
            await channel.send(content=message.content, embed=message.embed)

    # Decide if the purge of data in the database and riot API has reached the configured timeout.
    # If so, call the appropriate function
    def purge_encrypted_summoner_ids(self):
        current_time = time.time()
        if current_time - self.last_purge_encrypted_summoner_ids > self.purge_timeout_hours * 3600:
            logger.info('Purging encrypted summoner ids in the database')
            # Create the list of players to keep
            players_to_keep = []
            for guild in self.guilds.values():
                for player in guild.players:
                    players_to_keep.append(player)
            # Call riot api to perform the purge
            players_to_keep = list(set(players_to_keep))
            self.riot_api.purge_encrypted_summoner_ids(players_to_keep)
            self.last_purge_encrypted_summoner_ids = current_time

    # Select the best player to check the in game status in this iteration
    def select_player_to_check(self):
        player_to_check = None
        last_informed = math.inf
        for guild in self.guilds.values():
            for player in guild.players.values():
                if player.stopwatch.timeout_reached():
                    start_time = player.stopwatch.get_start_time()
                    if start_time < last_informed:
                        # This player is available to be checked, and was checked before the current best,
                        # so it is a better candidate
                        logger.debug(
                            f'Player {player.name} is a better candidate')
                        last_informed = start_time
                        player_to_check = player
                    else:
                        # This player is available to check, but has been checked more recently than others,
                        # so for the moment do not check it
                        logger.debug(
                            f'Rejecting player {player.name} as it has been checked more recently than others')
                else:
                    logger.debug(
                        f'Timeout still not reached for player {player.name}')
        # Here we in principle have selected the best option to check
        if player_to_check == None:
            logger.debug('Not checking any player during this iteration')
            return None
        else:
            logger.debug(
                f'Selecting player {player_to_check.name} to be checked')
            player_to_check.stopwatch.start()
            return player_to_check.name
