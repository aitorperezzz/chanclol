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
    # A unique player registered by the bot

    def __init__(self, id):
        # Id of the player. Corresponds to the encrypted summoner id in riot API
        self.id = id
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
        # Players registered in this guild together with the last game id
        # for which a message was sent for the player in the guild
        self.last_informed_game_ids = {}


class Bot:
    # The bot: receives commands from the discord client
    # and processes them. It runs an infinite loop that checks the
    # in-game status of all the players registered for each guild

    def __init__(self, client, riot_api_key):
        # Riot API class
        self.riot_api = riotapi.RiotApi(riot_api_key)
        # Keep a copy of the client
        self.client = client
        # Create the database
        self.database = database.Database()
        # Initialise the riot API with possible contents inside the database
        self.riot_api.set_database(self.database)
        # Initialise the guilds and the players from the database, if present
        self.guilds = self.database.get_guilds()
        self.players = self.database.get_players()
        # The bot will keep track of the last time player names were purged
        # in the database and the riot API
        self.last_purge_player_names = time.time()
        self.timeout_purge_player_names = 3

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
                response = await self.register(' '.join(parsed_input.arguments), guild)
            elif parsed_input.command == parsing.Command.UNREGISTER:
                response = await self.unregister(' '.join(parsed_input.arguments), guild)
            elif parsed_input.command == parsing.Command.PRINT:
                response = await self.print(guild)
            elif parsed_input.command == parsing.Command.CHANNEL:
                response = await self.channel(' '.join(parsed_input.arguments), guild)
            elif parsed_input.command == parsing.Command.HELP:
                response = message_formatter.create_help_message()
            else:
                raise ValueError('Command is not one of the possible ones')
            if response:
                await message.channel.send(content=response.content, embed=response.embed)

    # Register the provided player in the provided guild, if possible
    async def register(self, player_name, guild):

        # Get the player's id
        player_id = await self.riot_api.get_player_id(player_name)
        if player_id == None:
            logger.info(
                f'Riot has not provided an id for player {player_name}')
            return message_formatter.no_response_riot_api(player_name)

        # Check if the player already belongs to the guild
        if player_id in guild.last_informed_game_ids:
            logger.info(f'Player {player_name} is already registered')
            return message_formatter.player_already_registered(player_name)

        # Get rank info for this player
        league_info = await self.riot_api.get_league_info(player_id)
        if league_info == None:
            logger.info(
                f'Could not get rank info from Riot API for player {player_name}')
            return message_formatter.no_response_riot_api(player_name)

        # Now it's safe to register the player
        logger.info(f'Registering player {player_name}')
        # Add it to the list of players if necessary
        if not player_id in self.players:
            self.players[player_id] = Player(player_id)
        # Add it to the guild
        guild.last_informed_game_ids[player_id] = None
        self.database.add_player_to_guild(player_id, guild.id)

        # Send a final message
        logger.info(f'Player {player_name} has been registered')
        return message_formatter.player_registered(player_name, league_info)

    # Unregister a player from the guild
    async def unregister(self, player_name, guild):

        # Get the player's id
        player_id = await self.riot_api.get_player_id(player_name)
        if player_id == None:
            logger.info(
                f'Riot has not provided an id for player {player_name}')
            return message_formatter.no_response_riot_api(player_name)

        # Check if the player was registered in the guild
        if player_id in guild.last_informed_game_ids:
            logger.info(
                f'Unregistering player {player_name} from guild {guild.id}')
            del guild.last_informed_game_ids[player_id]
            self.database.remove_player_from_guild(player_id, guild.id)
            logger.info(f'Player {player_name} has been unregistered')
            # See if the player is in any other guild. If not, remove it completely
            guild_ids = self.get_guild_ids(player_id)
            if len(guild_ids) == 0:
                logger.info(f'Player {player_name} will be completely removed')
                del self.players[player_id]
            return message_formatter.player_unregistered_correctly(player_name)
        else:
            logger.info(
                f'Player {player_name} was not previously registered in this guild')
            return message_formatter.player_not_previously_registered(player_name)

    # Change the channel where the in-game messages will be sent to
    async def channel(self, new_channel_name, guild):
        discord_guild = self.client.get_guild(guild.id)
        # First make sure the channel does exist in the guild
        channel = discord.utils.get(
            discord_guild.channels, name=new_channel_name)
        if channel == None:
            logger.info(
                f'Cannot change channel to {new_channel_name} as it does not exist in the server')
            return message_formatter.channel_does_not_exist(new_channel_name)
        else:
            logger.info(
                f'Changing channel to use by this server to {new_channel_name}')
            guild.channel_id = channel.id
            self.database.set_channel_id(guild.id, guild.channel_id)
            logger.info(f'Channel changed to {new_channel_name}')
            return message_formatter.channel_changed(new_channel_name)

    # Print the players currently registered in the provided guild
    async def print(self, guild):
        channel_name = self.client.get_channel(guild.channel_id).name
        if channel_name == None:
            raise ValueError(
                f'Channel {channel_name} has not been found for this guild')
        # Create list of player names in this guild
        names = [self.riot_api.get_player_name(
            id) for id in guild.last_informed_game_ids]
        return message_formatter.print_config(names, channel_name)

    # Get a list of all the guild ids where the player is registered
    def get_guild_ids(self, player_id):
        guild_ids = []
        for guild in self.guilds.values():
            if player_id in guild.last_informed_game_ids:
                guild_ids.append(guild.id)
        return guild_ids

    # Main loop of the application
    async def loop_check_games(self):
        while True:
            # TODO: investigate if this wait time needs to be updated according to the number of users registered
            await asyncio.sleep(5)
            # Decide if the player names need to be purged
            self.purge_player_names()
            # Find a player to check in this iteration
            player_id = self.select_player_to_check()
            if player_id == None:
                continue
            player_name = self.riot_api.get_player_name(player_id)
            # We have a player to check
            logger.debug(f'Checking in game status of player {player_name}')
            # Make a request to Riot to check if the player is in game
            active_game_info = await self.riot_api.get_active_game_info(player_id)
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
            guild_ids_player = self.get_guild_ids(player_id)
            for guild_id in guild_ids_player:
                guild = self.guilds[guild_id]
                # Get the last game that was informed for this player in this guild
                last_informed_game_id = guild.last_informed_game_ids[player_id]
                if last_informed_game_id == active_game_info.game_id:
                    logger.debug(
                        f'Message for player {player_name} in guild {guild_id} for this game was already sent')
                else:
                    logger.info(
                        f'Player {player_name} is in game and a message has to be sent to guild {guild_id}')
                    # Update the last informed game_id
                    logger.info('Updating last informed game id')
                    guild.last_informed_game_ids[player_id] = active_game_info.game_id
                    self.database.set_last_informed_game_id(
                        player_id, guild.id, active_game_info.game_id)
                    # Create the complete response
                    message = message_formatter.in_game_message(
                        player_id, player_name, active_game_info)
                    await self.send_message(message, guild.channel_id)

    # Send the provided message in the provided channel id, if it exists
    async def send_message(self, message, channel_id):
        # Get the channel from channel id
        channel = self.client.get_channel(channel_id)
        if channel == None:
            logger.error(
                f'Could not find channel {channel_id} to send message to')
        else:
            await channel.send(content=message.content, embed=message.embed)

    # Decide if the purge of player names in the database and riot API has reached the configured timeout.
    # If so, do the corresponding job
    def purge_player_names(self):
        current_time = time.time()
        if current_time - self.last_purge_player_names < self.timeout_purge_player_names * 3600:
            return
        # Create the list of player ids we want to keep
        player_ids_to_keep = self.players.keys()
        # Perform the purge in the riot API and in the database
        logger.info('Purging player names')
        self.riot_api.purge_names(player_ids_to_keep)
        self.last_purge_player_names = current_time
        # TODO: update the names of the player ids we want to keep

    # Select the best player to check the in game status in this iteration
    def select_player_to_check(self):
        player_to_check = None
        last_informed = math.inf
        for player in self.players.values():
            if player.stopwatch.timeout_reached():
                start_time = player.stopwatch.get_start_time()
                if start_time < last_informed:
                    # This player is available to be checked, and was checked before the current best,
                    # so it is a better candidate
                    logger.debug(
                        f'Player {self.riot_api.get_player_name(player.id)} is a better candidate')
                    last_informed = start_time
                    player_to_check = player
                else:
                    # This player is available to check, but has been checked more recently than others,
                    # so for the moment do not check it
                    logger.debug(
                        f'Rejecting player {self.riot_api.get_player_name(player.id)} as it has been checked more recently')
            else:
                logger.debug(
                    f'Timeout still not reached for player {self.riot_api.get_player_name(player.id)}')
        # Here we in principle have selected the best option to check
        if player_to_check == None:
            logger.debug('Not checking any player during this iteration')
            return None
        else:
            logger.debug(
                f'Selecting player {self.riot_api.get_player_name(player_to_check.id)} to be checked')
            player_to_check.stopwatch.start()
            return player_to_check.id
