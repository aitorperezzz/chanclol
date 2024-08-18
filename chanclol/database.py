import sqlite3
import os
import bot
import logging

logger = logging.getLogger(__name__)


class Database:
    # Database class, used to access all the data inside the database
    def __init__(self, filename):
        self.filename = filename
        self.initialize()

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
            logger.info("Creating table champions")
            query = """CREATE TABLE champions (
                'champion_id' INT unsigned DEFAULT NULL,
                'name' VARCHAR(256) NOT NULL DEFAULT '',
                PRIMARY KEY ('champion_id'));"""
            self.execute_query(query)
            logger.info("Creating table riot_ids")
            query = """CREATE TABLE riot_ids (
                'puuid' VARCHAR(256) NOT NULL DEFAULT '',
                'game_name' VARCHAR(256) NOT NULL DEFAULT '',
                'tag_line' VARCHAR(256) NOT NULL DEFAULT '',
                PRIMARY KEY ('puuid'));"""
            self.execute_query(query)
            logger.info("Creating table summoner_ids")
            query = """CREATE TABLE summoner_ids (
                'puuid' VARCHAR(256) NOT NULL DEFAULT '',
                'summoner_id' VARCHAR(256) NOT NULL DEFAULT '',
                PRIMARY KEY ('puuid'));"""
            self.execute_query(query)
            logger.info("Creating table version")
            query = """CREATE TABLE version (
                'version' VARCHAR(256) DEFAULT '',
                PRIMARY KEY ('version'));"""
            self.execute_query(query)
            query = "INSERT INTO version (version) VALUES (?);"
            self.execute_query(query, ("",))
        else:
            logger.info("Database already present")
        return True

    # Decides if the database is already initialized (if the file is present)
    def initialized(self):
        return os.path.isfile(self.filename)

    # Executes a query into the database
    def execute_query(self, query, tuple=()):
        logger.debug(f"Executing query {query}")
        try:
            connection = sqlite3.connect(self.filename)
            cursor = connection.cursor()
            cursor.execute(query, tuple)
            result = cursor.fetchall()
            connection.commit()
            connection.close()
        except sqlite3.Error as error:
            logger.error(f"Could not execute query to the database: {query}")
            logger.error(str(error))
            return None
        return result

    # Prints the current status of the database
    def print_status(self):
        pass

    # Once the Riot API has downloaded the champions data, it will call this function
    # to store them
    def set_champions(self, champions):
        logger.info("Setting champions into the database")
        self.execute_query("DELETE FROM champions;")
        for id in champions:
            self.execute_query(
                "INSERT INTO champions (champion_id, name) VALUES (?, ?);",
                (
                    id,
                    champions[id],
                ),
            )

    # During initialisation, the Riot API will check if the database already has champions data
    def get_champions(self):
        logger.info("Getting champions from the database")
        query = "SELECT * FROM champions;"
        result = self.execute_query(query)
        champions = {}
        for element in result:
            champions[element[0]] = element[1]
        if len(champions) == 0:
            logger.info("Table champions is currently empty")
        return champions

    # Decides if the provided guild exists in the database
    def guild_exists(self, guild_id):
        result = self.execute_query(
            "SELECT * FROM guilds WHERE guild_id=?;", (guild_id,)
        )
        return len(result) == 1

    # Decides if the provided player exists in the database for the provided guild
    def player_exists(self, puuid, guild_id):
        result = self.execute_query(
            "SELECT * FROM players WHERE puuid=? AND guild_id=?;",
            (
                puuid,
                guild_id,
            ),
        )
        return len(result) == 1

    # Create the dictionary of guilds as stored in the database
    def get_guilds(self):
        logger.info("Getting guilds from the database")
        guilds_db = self.execute_query("SELECT * FROM guilds;")
        players_db = self.execute_query("SELECT * FROM players;")
        guilds = {}
        for guild_db in guilds_db:
            guild_id = guild_db[0]
            channel_id = guild_db[1]
            # Create the guild if it does not exist yet
            if not guild_id in guilds:
                guilds[guild_id] = bot.Guild(guild_id, channel_id)
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
    def get_players(self):

        logger.info("Getting players from the database")
        players_db = self.execute_query("SELECT * FROM players;")
        puuids = []
        for player_db in players_db:
            puuids.append(player_db[0])
        # Keep only unique players
        puuids = list(set(puuids))
        players = {}
        for puuid in puuids:
            players[puuid] = bot.Player(puuid)
        if len(players) == 0:
            logger.info("No players present in the database")
        return players

    # Adds a new guild to the database
    def add_guild(self, guild_id, channel_id):
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
    def add_player_to_guild(self, puuid, guild_id):
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
    def remove_player_from_guild(self, puuid, guild_id):
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
    def set_channel_id(self, guild_id, channel_id):
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
    def set_last_informed_game_id(self, puuid, guild_id, last_informed_game_id):
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
            "UPDATE players SET last_informed_game_id=? WHERE id=? AND guild_id=?;",
            (last_informed_game_id, puuid, guild_id),
        )

    # Get all the riot ids as stored in the database
    def get_riot_ids(self):
        logger.info("Getting riot ids")
        result = self.execute_query("SELECT * FROM riot_ids;")
        # Convert to a dictionary
        riot_ids = {}
        for element in result:
            riot_ids[element[0]] = (element[1], element[2])
        if len(riot_ids) == 0:
            logger.info("No riot ids present in the database")
        return riot_ids

    # Add a name to the database
    def add_riot_id(self, puuid, riot_id):
        logger.info(f"Adding riot id {riot_id} of player {puuid} to the database")
        self.execute_query(
            "INSERT INTO riot_ids (puuid, game_name, tag_line) VALUES (?, ?, ?);",
            (puuid, riot_id[0], riot_id[1]),
        )

    # Purges all the names from the database, except some that we need to keep
    def set_riot_ids(self, riot_ids):
        # Perform query into the database to delete the items we do not want
        query = "DELETE FROM riot_ids WHERE puuid NOT IN ({});".format(
            ", ".join("?" * len(riot_ids.keys()))
        )
        self.execute_query(query, tuple(riot_ids.keys()))
        query = "SELECT * FROM riot_ids;"
        final_number_players = self.execute_query(query)
        if len(final_number_players) != len(riot_ids.keys()):
            logger.error(
                "Final number of riot ids in the database is not as expected after purge"
            )
            return
        logger.info(
            f"Riot ids have been correctly purged, leaving {len(riot_ids.keys())}"
        )
        # Update the names of the players that are being kept
        for puuid in riot_ids:
            query = "UPDATE riot_ids SET game_name=? WHERE puuid=?;"
            self.execute_query(query, (riot_ids[puuid][0], puuid))
            query = "UPDATE riot_ids SET tag_line=? WHERE puuid=?;"
            self.execute_query(query, (riot_ids[puuid][1], puuid))

    def get_summoner_ids(self):
        logger.info("Getting summoner ids")
        result = self.execute_query("SELECT * FROM summoner_ids;")
        # Convert to a dictionary
        summoner_ids = {}
        for element in result:
            summoner_ids[element[0]] = element[1]
        if len(summoner_ids) == 0:
            logger.info("No summoner ids present in the database")
        return summoner_ids

    def add_summoner_id(self, puuid, summoner_id):
        logger.info(
            f"Adding summoner id {summoner_id} of player {puuid} to the database"
        )
        self.execute_query(
            "INSERT INTO summoner_ids (puuid, summoner_id) VALUES (?, ?);",
            (puuid, summoner_id),
        )

    # Purges all the names from the database, except some that we need to keep
    def set_summoner_ids(self, summoner_ids):
        # Perform query into the database to delete the items we do not want
        query = "DELETE FROM summoner_ids WHERE puuid NOT IN ({});".format(
            ", ".join("?" * len(summoner_ids.keys()))
        )
        self.execute_query(query, tuple(summoner_ids.keys()))
        query = "SELECT * FROM summoner_ids;"
        final_number_players = self.execute_query(query)
        if len(final_number_players) != len(summoner_ids.keys()):
            logger.error(
                "Final number of summoner ids in the database is not as expected after purge"
            )
            return
        logger.info(
            f"Summoner ids have been correctly purged, leaving {len(summoner_ids.keys())}"
        )
        # Update the names of the players that are being kept
        for puuid in summoner_ids:
            query = "UPDATE summoner_ids SET summoner_id=? WHERE puuid=?;"
            self.execute_query(query, (summoner_ids[puuid], puuid))

    # Get the current version of the patch
    def get_version(self):
        query = "SELECT * FROM version;"
        result = self.execute_query(query)
        if len(result) != 1:
            raise ValueError(
                "Table version in the database needs to contain one and only one value"
            )
        return result[0][0]

    # Update the value of the patch version
    def set_version(self, version):
        query = "UPDATE version SET version=?;"
        self.execute_query(query, (version,))
