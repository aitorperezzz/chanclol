import asyncio
import discord
import logging
import math

from riotapi.riotapi import RiotApi
import parser
import message_formatter as mft
from database.database_bot import DatabaseBot
from timed_executor import TimedExecutor
from guild import Guild
from player import Player
from riot_id import RiotId

logger = logging.getLogger(__name__)


# The bot: receives commands from the discord client
# and processes them. It runs an infinite loop that checks the
# in-game status of all the players registered for each guild
class Bot:

    def __init__(
        self,
        client,
        database_filename_bot: str,
        offline_threshold_mins: int,
        timeout_online_secs: int,
        timeout_offline_secs: int,
        main_loop_cycle_secs: int,
        riotapi_housekeeping_cycle_hrs: int,
        riotapi_key: str,
        database_filename_riotapi: str,
        restrictions: list[dict],
    ):

        # Keep a copy of the client
        self.client = client
        # Create the database
        self.database = DatabaseBot(database_filename_bot)
        # Initialise guilds and players from the database, if any
        self.guilds = self.database.get_guilds()
        self.players = self.database.get_players()
        # The bot executes a function by which it tells the riot API
        # which of the player ids to keep, so that the others can be purged
        self.riotapi_housekeeping_executor = TimedExecutor(
            riotapi_housekeeping_cycle_hrs * 60 * 60 * 1000, self.riotapi_housekeeping
        )
        # Timeouts for online and offline players
        self.offline_threshold_mins = offline_threshold_mins
        self.timeout_online_secs = timeout_online_secs
        self.timeout_offline_secs = timeout_offline_secs
        # Set default offline timeouts for all players
        for player in self.players.values():
            player.stopwatch.set_timeout(self.timeout_offline_secs * 1000)
        # Main loop cycle
        self.main_loop_cycle_secs = main_loop_cycle_secs
        # Riot API
        self.riot_api = RiotApi(riotapi_key, database_filename_riotapi, restrictions)

    # Main entry point for all messages
    async def receive(self, message):

        # Reject my own messages
        if message.author == self.client.user:
            logger.debug("Rejecting message sent by myself")
            return

        # For the time being, ignore messages sent on private channels
        if not message.guild:
            logger.info("Ignoring private message")
            await message.channel.send(
                "For the time being, I am ignoring private messages"
            )
            return

        # Register a guild in case it does not yet exist
        if not message.guild.id in self.guilds:
            logger.info(f"Initialising guild {message.guild.id}")
            self.guilds[message.guild.id] = Guild(message.guild.id, message.channel.id)
            self.database.add_guild(message.guild.id, message.channel.id)
            logger.info("Sending welcome message")
            response = mft.welcome(message.channel.name)
            await message.channel.send(content=response.content, embed=response.embed)
        guild = self.guilds[message.guild.id]

        # Parse the input provided and call the appropriate function
        logger.debug(f"Message received: {message.content}")
        parsed_input = parser.Parser(message.content)
        match parsed_input.code:
            case parser.Result.NO_BOT_PREFIX:
                logger.debug("Rejecting message not intended for the bot")
            case parser.Result.OK:
                logger.info(f"Command understood: {message.content}")
                match parsed_input.command:
                    case parser.Command.REGISTER:
                        responses = await self.register(
                            RiotId(
                                parsed_input.arguments[0], parsed_input.arguments[1]
                            ),
                            guild,
                        )
                    case parser.Command.UNREGISTER:
                        responses = await self.unregister(
                            RiotId(
                                parsed_input.arguments[0], parsed_input.arguments[1]
                            ),
                            guild,
                        )
                    case parser.Command.PRINT:
                        responses = await self.print(guild)
                    case parser.Command.CHANNEL:
                        responses = await self.channel(parsed_input.arguments[0], guild)
                    case parser.Command.HELP:
                        responses = [mft.create_help_message()]
                    case parser.Command.RANK:
                        responses = await self.rank(
                            RiotId(parsed_input.arguments[0], parsed_input.arguments[1])
                        )
                    case _:
                        raise ValueError("Command is not one of the possible ones")
                for response in responses:
                    await message.channel.send(
                        content=response.content, embed=response.embed
                    )
            case _:
                error_message = parsed_input.error_message
                if not error_message:
                    raise ValueError(
                        "Expected an error message in a parse failure case"
                    )
                else:
                    logger.info(
                        f"Wrong input: '{message.content}'. Reason: {error_message}"
                    )
                    response = mft.input_not_valid(error_message)
                    await message.channel.send(
                        content=response.content, embed=response.embed
                    )

    # Register the provided player in the provided guild, if possible
    async def register(self, riot_id: RiotId, guild: Guild) -> list[mft.Message]:

        # Get the puuid
        puuid = await self.riot_api.get_puuid(riot_id)
        if not puuid:
            logger.info(f"Riot has not provided a puuid for player {riot_id}")
            return [mft.no_response_riot_api(riot_id)]

        # Check if the player already belongs to the guild
        if puuid in guild.last_informed_game_ids:
            logger.info(f"Player {riot_id} is already registered")
            return [mft.player_already_registered(riot_id)]

        # Get rank info for this player
        league = await self.riot_api.get_leagues(puuid)
        if not league:
            logger.info(f"Could not get rank from Riot API for player {riot_id}")

        # Now it's safe to register the player
        logger.info(f"Registering player {riot_id}")
        # Add it to the list of players if necessary
        if not puuid in self.players:
            self.players[puuid] = Player(puuid)
            self.players[puuid].stopwatch.set_timeout(self.timeout_offline_secs * 1000)
        # Add to the guild
        guild.last_informed_game_ids[puuid] = None
        # Add to the database
        self.database.add_player_to_guild(puuid, guild.id)

        # Send a final message
        logger.info(f"Player {riot_id} has been registered")
        return [
            mft.player_registered(riot_id),
            mft.player_rank(riot_id, league),
        ]

    # Unregister a player from the guild
    async def unregister(self, riot_id: RiotId, guild: Guild) -> list[mft.Message]:

        # Get the puuid
        puuid = await self.riot_api.get_puuid(riot_id)
        if puuid == None:
            logger.info(f"Riot has not provided an id for player {riot_id}")
            return [mft.no_response_riot_api(riot_id)]

        # Check if the player was registered in the guild
        if puuid in guild.last_informed_game_ids:
            logger.info(f"Unregistering player {riot_id} from guild {guild.id}")
            del guild.last_informed_game_ids[puuid]
            # Remove from the database
            self.database.remove_player_from_guild(puuid, guild.id)
            logger.info(f"Player {riot_id} has been unregistered")
            # See if the player is in any other guild. If not, remove it completely
            guild_ids = self.get_guild_ids(puuid)
            if len(guild_ids) == 0:
                logger.info(f"Player {riot_id} will be completely removed")
                del self.players[puuid]
            return [mft.player_unregistered_correctly(riot_id)]
        else:
            logger.info(f"Player {riot_id} was not previously registered in this guild")
            return [mft.player_not_previously_registered(riot_id)]

    # Print the rank of a player, if it exists
    async def rank(self, riot_id: RiotId) -> list[mft.Message]:

        # Get the puuid
        puuid = await self.riot_api.get_puuid(riot_id)
        if not puuid:
            logger.info(f"Riot has not provided an id for player {riot_id}")
            return [mft.no_response_riot_api(riot_id)]

        # Get rank info for this player
        league = await self.riot_api.get_leagues(puuid)
        if not league:
            logger.info(f"Could not get rank info from Riot API for player {riot_id}")
            return [mft.no_response_riot_api(riot_id)]

        # Send a final message
        logger.info(f"Sending rank of player {riot_id}")
        return [mft.player_rank(riot_id, league)]

    # Change the channel where the in-game messages will be sent to
    async def channel(self, new_channel_name: str, guild: Guild) -> list[mft.Message]:

        discord_guild = self.client.get_guild(guild.id)
        # First make sure the channel does exist in the guild
        channel = discord.utils.get(discord_guild.channels, name=new_channel_name)
        if channel == None:
            logger.info(
                f"Cannot change channel to {new_channel_name} as it does not exist in the server"
            )
            return [mft.channel_does_not_exist(new_channel_name)]
        else:
            logger.info(f"Changing channel to use by this server to {new_channel_name}")
            guild.channel_id = channel.id
            self.database.set_channel_id(guild.id, guild.channel_id)
            logger.info(f"Channel changed to {new_channel_name}")
            return [mft.channel_changed(new_channel_name)]

    # Print the players currently registered in the provided guild
    async def print(self, guild: Guild) -> list[mft.Message]:

        # Very bad error if I cannot find the name of the channel to which
        # I am sending the messages
        channel_name = self.client.get_channel(guild.channel_id).name
        if channel_name == None:
            raise ValueError(
                f"Channel {channel_name} has not been found for this guild"
            )
        # Create list of player names in this guild
        riot_ids = []
        for puuid in guild.last_informed_game_ids:
            riot_id = await self.riot_api.get_riot_id(puuid)
            if riot_id:
                riot_ids.append(riot_id)
        return [mft.print_config(riot_ids, channel_name)]

    # Get a list of all the guild ids where the provided player is registered
    def get_guild_ids(self, puuid: str) -> list[int]:

        return [
            guild.id
            for guild in self.guilds.values()
            if puuid in guild.last_informed_game_ids
        ]

    # Main loop of the application
    async def loop(self):

        while True:
            # TODO: investigate if this wait time needs to be updated according to the number of users registered
            await asyncio.sleep(self.main_loop_cycle_secs)
            # Perform housekeeping of the riot API if necessary
            await self.riotapi_housekeeping_executor.execute()
            # Find a player to check in this iteration
            puuid = await self.select_player_to_check()
            if not puuid:
                continue
            riot_id = await self.riot_api.get_riot_id(puuid)
            if not riot_id:
                logger.error(f"Could not find a riot id for puuid {puuid}")
                continue
            # We have a player to check
            logger.debug(f"Checking in game status of player {riot_id}")
            # Make a request to Riot to check if the player is in game
            spectator = await self.riot_api.get_spectator(puuid)
            # At this point the request has been made in some form, so reset the stopwatch
            self.players[puuid].stopwatch.start()
            if not spectator:
                logger.debug(f"Spectator data for player {riot_id} is not available")
                # Player is offline, update the timeout if needed
                if self.players[puuid].update_check_timeout(
                    False,
                    self.offline_threshold_mins,
                    self.timeout_online_secs,
                    self.timeout_offline_secs,
                ):
                    logger.info(f"Player {riot_id} is now offline")
                continue
            # Player is online, update the timeout if needed
            if self.players[puuid].update_check_timeout(
                True,
                self.offline_threshold_mins,
                self.timeout_online_secs,
                self.timeout_offline_secs,
            ):
                logger.info(f"Player {riot_id} is now online")
            # Get the guilds where this player is registered
            guild_ids_player = self.get_guild_ids(puuid)
            for guild_id in guild_ids_player:
                guild = self.guilds[guild_id]
                # Get the last game that was informed for this player in this guild
                last_informed_game_id = guild.last_informed_game_ids[puuid]
                if last_informed_game_id == spectator.game_id:
                    logger.debug(
                        f"Message for player {riot_id} in guild {guild_id} for this game was already sent"
                    )
                else:
                    logger.info(
                        f"Player {riot_id} is in game and a message has to be sent to guild {guild_id}"
                    )
                    # Create the complete response
                    message = mft.in_game_message(puuid, riot_id, spectator)
                    if not message:
                        logger.error(
                            f"Could not produce an in game message for player with riot id {riot_id}"
                        )
                        continue
                    await self.send_message(message, guild.channel_id)
                    # Update the last informed game_id
                    logger.info("Updating last informed game id")
                    guild.last_informed_game_ids[puuid] = spectator.game_id
                    self.database.set_last_informed_game_id(
                        puuid, guild.id, spectator.game_id
                    )

    # Send the provided message in the provided channel id, if it exists
    async def send_message(self, message, channel_id: int) -> None:

        # Get the channel from channel id
        channel = self.client.get_channel(channel_id)
        if channel == None:
            logger.error(f"Could not find channel {channel_id} to send message to")
        else:
            await channel.send(content=message.content, embed=message.embed)

    # Perform housekeeping tasks on the Riot API
    async def riotapi_housekeeping(self) -> None:

        logger.info("Riot API housekeeping")
        # Create the list of player ids we want to keep
        player_ids_to_keep = list(self.players.keys())
        # Perform housekeeping in the Riot API
        await self.riot_api.housekeeping(player_ids_to_keep)

    # Select the player for which we will request the spectator data
    # As a rule of thumb, it will be the player for which we have not had this data
    # for the longer time.
    # Online players will be checked more frequently
    async def select_player_to_check(self) -> str | None:

        puuid_to_check: str | None = None
        best_time_behind = -math.inf
        for player in self.players.values():
            time_behind = player.stopwatch.time_behind()
            riot_id = await self.riot_api.get_riot_id(player.id)
            if time_behind > 0:
                if time_behind > best_time_behind:
                    # This player is available to be checked, and is more behind than the best,
                    # so it is the new best
                    logger.debug(f"Player {riot_id} is more behind")
                    best_time_behind = time_behind
                    puuid_to_check = player.id
                else:
                    # This player is available to check, but is less behind than the current best
                    logger.debug(f"Rejecting player {riot_id} as it is less behind")
            else:
                logger.debug(f"Timeout still not reached for player {riot_id}")
        # Here we in principle have selected the best option to check
        if not puuid_to_check:
            logger.debug("Not checking any player during this iteration")
            return None
        else:
            riot_id_to_check = await self.riot_api.get_riot_id(puuid_to_check)
            if not riot_id_to_check:
                logger.warning(
                    f"Selected player with id {puuid_to_check} to check, but could not find their riot id"
                )
            else:
                logger.debug(f"Will check status of player {riot_id_to_check}")
            return puuid_to_check
