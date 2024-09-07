import logging

from database import Database
from player import Player
from guild import Guild

logger = logging.getLogger(__name__)


class DatabaseBot(Database):

    # Initializes the database
    def initialize(self):
        logger.info("Initialising database")
        if not self.initialized():
            logger.info("Creating tables in database")
            logger.info("Creating table guilds")
            query = """CREATE TABLE guilds (
                'guild_id' INT unsigned DEFAULT NULL,
                'channel_id' INT unsigned DEFAULT NULL,
                PRIMARY KEY ('guild_id'));"""
            self.execute_query(query)
            logger.info("Creating table players")
            query = """CREATE TABLE players (
                'puuid' VARCHAR(256) NOT NULL DEFAULT '',
                'guild_id' INT unsigned DEFAULT NULL,
                'last_informed_game_id' INT unsigned DEFAULT NULL,
                PRIMARY KEY ('puuid', 'guild_id'));"""
            self.execute_query(query)
        else:
            logger.info("Database already present")
        return True

    # Decides if the provided guild exists in the database
    def guild_exists(self, guild_id: str) -> bool:

        result = self.execute_query(
            "SELECT * FROM guilds WHERE guild_id=?;", (guild_id,)
        )
        return len(result) == 1

    # Decides if the provided player exists in the database for the provided guild
    def player_exists(self, puuid: str, guild_id: str) -> bool:

        result = self.execute_query(
            "SELECT * FROM players WHERE puuid=? AND guild_id=?;",
            (
                puuid,
                guild_id,
            ),
        )
        return len(result) == 1

    # Create the dictionary of guilds as stored in the database
    def get_guilds(self) -> dict:

        logger.info("Getting guilds from the database")
        guilds_db = self.execute_query("SELECT * FROM guilds;")
        players_db = self.execute_query("SELECT * FROM players;")
        guilds = {}
        for guild_db in guilds_db:
            guild_id = guild_db[0]
            channel_id = guild_db[1]
            # Create the guild if it does not exist yet
            if not guild_id in guilds:
                guilds[guild_id] = Guild(guild_id, channel_id)
        # Add players to the guilds
        for player_db in players_db:
            puuid = player_db[0]
            guild_id = player_db[1]
            last_informed_game_id = player_db[2]
            if not guild_id in guilds:
                logger.error(
                    f"Player's guild id {guild_id} does not exist in the database"
                )
                continue
            if puuid in guilds[guild_id].last_informed_game_ids:
                logger.error(f"Player {puuid} is already one of the guild's players")
                continue
            guilds[guild_id].last_informed_game_ids[puuid] = last_informed_game_id
        if len(guilds) == 0:
            logger.info("No guilds present in the database")
        return guilds

    # Create the dictionary of players as stored in the database
    def get_players(self) -> dict:

        logger.info("Getting players from the database")
        players_db = self.execute_query("SELECT * FROM players;")
        puuids = []
        for player_db in players_db:
            puuids.append(player_db[0])
        # Keep only unique players
        puuids = list(set(puuids))
        players = {}
        for puuid in puuids:
            players[puuid] = Player(puuid)
        if len(players) == 0:
            logger.info("No players present in the database")
        return players

    # Adds a new guild to the database
    def add_guild(self, guild_id: int, channel_id: str) -> None:

        logger.info(f"Adding guild {guild_id} to the database")
        if self.guild_exists(guild_id):
            logger.error(f"Cannot add guild {guild_id} as it already exists")
            return
        self.execute_query(
            "INSERT INTO guilds (guild_id, channel_id) VALUES (?, ?);",
            (
                guild_id,
                channel_id,
            ),
        )

    # Adds the specified player to the specified guild
    def add_player_to_guild(self, puuid: str, guild_id: int) -> None:

        logger.info(f"Adding player {puuid} to guild {guild_id}")
        if not self.guild_exists(guild_id):
            logger.error(f"Cannot add player to guild {guild_id} as it does not exist")
            return
        # Execute query to add player
        self.execute_query(
            "INSERT INTO players (puuid, guild_id) VALUES (?, ?);",
            (
                puuid,
                guild_id,
            ),
        )

    # Removes a player from the provided guild
    def remove_player_from_guild(self, puuid: str, guild_id: int) -> None:

        logger.info(f"Removing player {puuid} from guild {guild_id}")
        if not self.guild_exists(guild_id):
            logger.error(
                f"Cannot remove player from guild {guild_id} as it does not exist"
            )
            return
        if not self.player_exists(puuid, guild_id):
            logger.error(f"Cannot remove player {puuid} as it does not exist")
            return
        # Execute query to remove player
        self.execute_query(
            "DELETE FROM players WHERE puuid=? AND guild_id=?;",
            (
                puuid,
                guild_id,
            ),
        )

    # Changes the channel id for the specified guild
    def set_channel_id(self, guild_id: int, channel_id: str) -> None:

        logger.info(f"Setting channel id {channel_id} for guild {guild_id}")
        if not self.guild_exists(guild_id):
            logger.error(
                f"Cannot set channel id of guild {guild_id} as it does not exist"
            )
            return
        # Change channel
        self.execute_query(
            "UPDATE guilds SET channel_id=? WHERE guild_id=?;", (channel_id, guild_id)
        )

    # Changes the last informed game id of the specified player in the specified guild
    def set_last_informed_game_id(
        self, puuid: str, guild_id: int, last_informed_game_id: int
    ):

        logger.info(
            f"Setting last informed game id for player {puuid} in guild {guild_id} to {last_informed_game_id}"
        )
        # Check the player does exist in the guild
        if not self.player_exists(puuid, guild_id):
            logger.error(
                f"Cannot set last informed game id of player {puuid} as it does not exist"
            )
            return
        # Change last informed game id
        self.execute_query(
            "UPDATE players SET last_informed_game_id=? WHERE puuid=? AND guild_id=?;",
            (last_informed_game_id, puuid, guild_id),
        )
