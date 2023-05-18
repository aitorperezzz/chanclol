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
        logger.info('Initialising database')
        if not self.initialized():
            logger.info('Creating tables in database')
            logger.info('Creating table guilds')
            query = """CREATE TABLE guilds (
                'id' INT unsigned DEFAULT NULL,
                'channel_id' INT unsigned DEFAULT NULL,
                PRIMARY KEY ('id'));"""
            self.execute_query(query)
            logger.info('Creating table players')
            query = """CREATE TABLE players (
                'id' VARCHAR(256) NOT NULL DEFAULT '',
                'guild_id' INT unsigned DEFAULT NULL,
                'last_informed_game_id' INT unsigned DEFAULT NULL,
                PRIMARY KEY ('id', 'guild_id'));"""
            self.execute_query(query)
            logger.info('Creating table champions')
            query = """CREATE TABLE champions (
                'id' INT unsigned DEFAULT NULL,
                'name' VARCHAR(256) NOT NULL DEFAULT '',
                PRIMARY KEY ('id'));"""
            self.execute_query(query)
            logger.info('Creating table spells')
            query = """CREATE TABLE spells (
                'id' INT unsigned DEFAULT NULL,
                'name' VARCHAR(256) NOT NULL DEFAULT '',
                PRIMARY KEY ('id'));"""
            self.execute_query(query)
            logger.info('Creating table names')
            query = """CREATE TABLE names (
                'id' VARCHAR(256) NOT NULL DEFAULT '',
                'name' VARCHAR(256) NOT NULL DEFAULT '',
                PRIMARY KEY ('id'));"""
            self.execute_query(query)
            logger.info('Creating table version')
            query = """CREATE TABLE version (
                'version' VARCHAR(256) DEFAULT '',
                PRIMARY KEY ('version'));"""
            self.execute_query(query)
        else:
            logger.info('Database already present')
        return True

    # Decides if the database is already initialized (if the file is present)
    def initialized(self):
        return os.path.isfile(self.filename)

    # Executes a query into the database
    def execute_query(self, query, tuple=()):
        logger.debug(f'Executing query {query}')
        try:
            connection = sqlite3.connect(self.filename)
            cursor = connection.cursor()
            cursor.execute(query, tuple)
            result = cursor.fetchall()
            connection.commit()
            connection.close()
        except sqlite3.Error as error:
            logger.error(f'Could not execute query to the database: {query}')
            logger.error(str(error))
            return None
        return result

    # Prints the current status of the database
    def print_status(self):
        pass

    # Once the Riot API has downloaded the champions data, it will call this function
    # to store them
    def set_champions(self, champions):
        logger.info('Setting champions into the database')
        self.execute_query('DELETE FROM champions;')
        for id in champions:
            self.execute_query(
                'INSERT INTO champions (id, name) VALUES (?, ?);', (id, champions[id],))

    # During initialisation, the Riot API will check if the database already has champions data
    def get_champions(self):
        logger.info('Getting champions from the database')
        query = 'SELECT * FROM champions;'
        result = self.execute_query(query)
        champions = {}
        for element in result:
            champions[element[0]] = element[1]
        if len(champions) == 0:
            logger.info('Table champions is currently empty')
        return champions

    # Once the Riot API has downloaded the spells data, it will call this function
    # to store them
    def set_spells(self, spells):
        logger.info('Setting spells into the database')
        self.execute_query('DELETE FROM spells;')
        for id in spells:
            self.execute_query(
                'INSERT INTO spells (id, name) VALUES (?, ?);', (id, spells[id],))

    # During initialisation, the Riot API will check if the database already has champions data
    def get_spells(self):
        logger.info('Getting spells from the database')
        query = 'SELECT * FROM spells;'
        result = self.execute_query(query)
        spells = {}
        for element in result:
            spells[element[0]] = element[1]
        if len(spells) == 0:
            logger.info('Table spells is currently empty')
        return spells

    # Decides if the provided guild exists in the database
    def guild_exists(self, guild_id):
        result = self.execute_query(
            'SELECT * FROM guilds WHERE id=?;', (guild_id,))
        return len(result) == 1

    # Decides if the provided player exists in the database for the provided guild
    def player_exists(self, player_id, guild_id):
        result = self.execute_query(
            'SELECT * FROM players WHERE id=? AND guild_id=?;', (player_id, guild_id,))
        return len(result) == 1

    # Create the dictionary of guilds as stored in the database
    def get_guilds(self):
        logger.info('Getting guilds from the database')
        guilds_db = self.execute_query('SELECT * FROM guilds;')
        players_db = self.execute_query('SELECT * FROM players;')
        guilds = {}
        for guild_db in guilds_db:
            guild_id = guild_db[0]
            channel_id = guild_db[1]
            # Create the guild if it does not exist yet
            if not guild_id in guilds:
                guilds[guild_id] = bot.Guild(guild_id, channel_id)
        # Add players to the guilds
        for player_db in players_db:
            player_id = player_db[0]
            player_guild = player_db[1]
            last_informed_game_id = player_db[2]
            if not player_guild in guilds:
                logger.error(
                    f'Player\'s guild id {player_guild} does not exist in the database')
                continue
            if player_id in guilds[player_guild].last_informed_game_ids:
                logger.error(
                    f'Player {player_id} is already one of the guild\'s players')
                continue
            guilds[player_guild].last_informed_game_ids[player_id] = last_informed_game_id
        if len(guilds) == 0:
            logger.info('No guilds present in the database')
        return guilds

    # Create the dictionary of players as stored in the database
    def get_players(self):
        logger.info('Getting players from the database')
        players_db = self.execute_query('SELECT * FROM players;')
        player_ids = []
        for player_db in players_db:
            player_ids.append(player_db[0])
        # Keep only unique players
        player_ids = list(set(player_ids))
        players = {}
        for id in player_ids:
            players[id] = bot.Player(id)
        if len(players) == 0:
            logger.info('No players present in the database')
        return players

    # Adds a new guild to the database
    def add_guild(self, guild_id, channel_id):
        logger.info(f'Adding guild {guild_id} to the database')
        if self.guild_exists(guild_id):
            logger.error(f'Cannot add guild {guild_id} as it already exists')
            return
        self.execute_query(
            'INSERT INTO guilds (id, channel_id) VALUES (?, ?);', (guild_id, channel_id,))

    # Adds the specified player to the specified guild
    def add_player_to_guild(self, player_id, guild_id):
        logger.info(f'Adding player {player_id} to guild {guild_id}')
        if not self.guild_exists(guild_id):
            logger.error(
                f'Cannot add player to guild {guild_id} as it does not exist')
            return
        # Execute query to add player
        self.execute_query(
            'INSERT INTO players (id, guild_id) VALUES (?, ?);', (player_id, guild_id,))

    # Removes a player from the provided guild
    def remove_player_from_guild(self, player_id, guild_id):
        logger.info(f'Removing player {player_id} from guild {guild_id}')
        if not self.guild_exists(guild_id):
            logger.error(
                f'Cannot remove player from guild {guild_id} as it does not exist')
            return
        if not self.player_exists(player_id, guild_id):
            logger.error(
                f'Cannot remove player {player_id} as it does not exist')
            return
        # Execute query to remove player
        self.execute_query(
            'DELETE FROM players WHERE id=? AND guild_id=?;', (player_id, guild_id,))

    # Changes the channel id for the specified guild
    def set_channel_id(self, guild_id, channel_id):
        logger.info(f'Setting channel id {channel_id} for guild {guild_id}')
        if not self.guild_exists(guild_id):
            logger.error(
                f'Cannot set channel id of guild {guild_id} as it does not exist')
            return
        # Change channel
        self.execute_query(
            'UPDATE guilds SET channel_id=? WHERE id=?;', (channel_id, guild_id))

    # Changes the last informed game id of the specified player in the specified guild
    def set_last_informed_game_id(self, player_id, guild_id, last_informed_game_id):
        logger.info(
            f'Setting last informed game id for player {player_id} in guild {guild_id} to {last_informed_game_id}')
        # Check the player does exist in the guild
        if not self.player_exists(player_id, guild_id):
            logger.error(
                f'Cannot set last informed game id of player {player_id} as it does not exist')
            return
        # Change last informed game id
        self.execute_query(
            'UPDATE players SET last_informed_game_id=? WHERE id=? AND guild_id=?;', (last_informed_game_id, player_id, guild_id))

    # Get all the player names as stored in the database
    def get_names(self):
        logger.info('Getting names')
        result = self.execute_query('SELECT * FROM names;')
        # Convert to a dictionary
        names = {}
        for element in result:
            names[element[0]] = element[1]
        if len(names) == 0:
            logger.info(
                'No names present in the database')
        return names

    # Add a name to the database
    def add_name(self, player_id, player_name):
        logger.info(
            f'Adding name {player_name} of player {player_id} to the database')
        self.execute_query(
            'INSERT INTO names (id, name) VALUES (?, ?);',
            (player_id, player_name))

    # Purges all the names from the database, except some that we need to keep
    def update_names(self, names_to_keep):
        # Perform query into the database to delete the items we do not want
        query = 'DELETE FROM names WHERE id NOT IN ({});'.format(
            ', '.join('?' * len(names_to_keep.keys())))
        self.execute_query(query, tuple(names_to_keep.keys()))
        query = 'SELECT * FROM names;'
        final_number_players = self.execute_query(query)
        if len(final_number_players) != len(names_to_keep.keys()):
            logger.error(
                'Final number of player names in the database is not as expected after purge')
            return
        logger.info(
            f'Names have been correctly purged, leaving {len(names_to_keep.keys())} players')
        # Update the names of the players that are being kept
        for id in names_to_keep:
            query = 'UPDATE names SET name=? WHERE id=?;'
            self.execute_query(query, (names_to_keep[id], id))

    # Get the current version of the patch
    def get_version(self):
        query = 'SELECT * FROM version;'
        result = self.execute_query(query)
        if len(result) != 1:
            raise ValueError(
                'Table version in the database needs to contain one and only one value')
        return result[0][0]

    # Update the value of the patch version
    def set_version(self, version):
        query = 'UPDATE version SET version=?;'
        self.execute_query(query, (version,))
