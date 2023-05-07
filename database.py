import sqlite3
import os
import bot


class Database:
    # Database class, used to access all the data inside the database
    def __init__(self):
        self.filename = 'chanclol.db'
        self.initialize()

    # Initializes the database
    def initialize(self):
        if not self.initialized():
            print('Creating tables in database')
            print('Creating table: guilds')
            query = """CREATE TABLE guilds (
                'id' INT unsigned DEFAULT NULL,
                'channel_id' INT unsigned DEFAULT NULL,
                PRIMARY KEY ('id'));"""
            self.execute_query(query)
            print('Creating table: players')
            query = """CREATE TABLE players (
                'name' VARCHAR(256) NOT NULL DEFAULT '',
                'guild_id' INT unsigned DEFAULT NULL,
                'last_informed_game_id' INT unsigned DEFAULT NULL,
                PRIMARY KEY ('name', 'guild_id'));"""
            self.execute_query(query)
            print('Creating table: champions')
            query = """CREATE TABLE champions (
                'id' INT unsigned DEFAULT NULL,
                'name' VARCHAR(256) NOT NULL DEFAULT '',
                PRIMARY KEY ('id'));"""
            self.execute_query(query)
            print('Creating table: spells')
            query = """CREATE TABLE spells (
                'id' INT unsigned DEFAULT NULL,
                'name' VARCHAR(256) NOT NULL DEFAULT '',
                PRIMARY KEY ('id'));"""
            self.execute_query(query)
            print('Creating table: encrypted_summoner_ids')
            query = """CREATE TABLE encrypted_summoner_ids (
                'name' VARCHAR(256) NOT NULL DEFAULT '',
                'encrypted_summoner_id' VARCHAR(256) NOT NULL DEFAULT '',
                PRIMARY KEY ('name'));"""
            self.execute_query(query)
        else:
            print('Database already present')
        return True

    # Decides if the database is already initialized (if the file is present)
    def initialized(self):
        return os.path.isfile(self.filename)

    # Executes a query into the database
    def execute_query(self, query, tuple=()):
        try:
            connection = sqlite3.connect(self.filename)
            cursor = connection.cursor()
            cursor.execute(query, tuple)
            result = cursor.fetchall()
            connection.commit()
            connection.close()
        except sqlite3.Error as error:
            print('DATABASE ERROR: could not execute query')
            print(str(error))
            return None
        return result

    # Prints the current status of the database
    def print_status(self):
        pass

    # Once the Riot API has downloaded the champions data, it will call this function
    # to store them
    def set_champions(self, champions):
        self.execute_query('DELETE FROM champions;')
        for id in champions:
            self.execute_query(
                'INSERT INTO champions (id, name) VALUES (?, ?);', (id, champions[id],))

    # During initialisation, the Riot API will check if the database already has champions data
    def get_champions(self):
        query = 'SELECT * FROM champions;'
        result = self.execute_query(query)
        champions = {}
        for element in result:
            champions[element[0]] = element[1]
        if len(champions) == 0:
            print('The database does not contain champions currently')
        return champions

    # Once the Riot API has downloaded the spells data, it will call this function
    # to store them
    def set_spells(self, spells):
        self.execute_query('DELETE FROM spells;')
        for id in spells:
            self.execute_query(
                'INSERT INTO spells (id, name) VALUES (?, ?);', (id, spells[id],))

    # During initialisation, the Riot API will check if the database already has champions data
    def get_spells(self):
        query = 'SELECT * FROM spells;'
        result = self.execute_query(query)
        spells = {}
        for element in result:
            spells[element[0]] = element[1]
        if len(spells) == 0:
            print('The database does not contain spells currently')
        return spells

    # Decides if the provided guild exists in the database
    def guild_exists(self, guild_id):
        result = self.execute_query(
            'SELECT * FROM guilds WHERE id=?;', (guild_id,))
        return len(result) == 1

    # Decides if the provided player exists in the database for the provided guild
    def player_exists(self, player_name, guild_id):
        result = self.execute_query(
            'SELECT * FROM players WHERE name=? AND guild_id=?;', (player_name, guild_id,))
        return len(result) == 1

    # Get the guilds as stored in the database
    def get_guilds(self):
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
            player_name = player_db[0]
            player_guild = player_db[1]
            player_last_informed_game_id = player_db[2]
            if not player_guild in guilds:
                print('Error, player\'s guild id does not exist inside the guilds table')
                continue
            if player_name in guilds[player_guild].players:
                print('Error, player already exists in the guild\'s players')
                continue
            guilds[player_guild].players[player_name] = bot.Player(player_name)
            guilds[player_guild].players[player_name].last_informed_game_id = player_last_informed_game_id

        if len(guilds) == 0:
            print('The database does not contain guilds currently')
        return guilds

    # Adds a new guild to the database
    def add_guild(self, guild_id, channel_id):
        if self.guild_exists(guild_id):
            print('Error, cannot add guild that already exists')
            return
        self.execute_query(
            'INSERT INTO guilds (id, channel_id) VALUES (?, ?);', (guild_id, channel_id,))

    # Adds the specified player to the specified guild
    def add_player_to_guild(self, guild_id, player_name):
        if not self.guild_exists(guild_id):
            print('Cannot add player to guild that does not exist')
            return
        # Execute query to add player
        self.execute_query(
            'INSERT INTO players (name, guild_id) VALUES (?, ?);', (player_name, guild_id,))

    # Removes a player from the provided guild
    def remove_player_from_guild(self, guild_id, player_name):
        if not self.guild_exists(guild_id):
            print('Cannot remove player from guild that does not exist')
            return
        if not self.player_exists(player_name, guild_id):
            print('Cannot remove player that does not exist')
            return
        # Execute query to remove player
        self.execute_query(
            'DELETE FROM players WHERE name=? AND guild_id=?;', (player_name, guild_id,))

    # Changes the channel id for the specified guild
    def set_channel_id(self, guild_id, channel_id):
        if not self.guild_exists(guild_id):
            print('Cannot set channel id of guild that does not exist')
            return
        # Change channel
        self.execute_query(
            'UPDATE guilds SET channel_id=? WHERE id=?;', (channel_id, guild_id))

    # Changes the last informed game id of the specified player
    def set_last_informed_game_id(self, player_name, guild_id, last_informed_game_id):
        # Check the player does exist in the database
        if not self.player_exists(player_name, guild_id):
            print('Cannot set last informed game id of player that does not exist')
            return
        # Change last informed game id
        self.execute_query(
            'UPDATE players SET last_informed_game_id=? WHERE name=? AND guild_id=?;', (last_informed_game_id, player_name, guild_id))

    # Get all the encrypted summoner ids stored in the database
    def get_encrypted_summoner_ids(self):
        result = self.execute_query('SELECT * FROM encrypted_summoner_ids;')
        # Convert to a dictionary
        encrypted_summoner_ids = {}
        for element in result:
            encrypted_summoner_ids[element[0]] = element[1]
        if len(encrypted_summoner_ids) == 0:
            print(
                'The database does not contain encrypted summoner ids currently')
        return encrypted_summoner_ids

    # Add a new encrypted summoner id to the database
    def add_encrypted_summoner_id(self, player_name, encrypted_summoner_id):
        self.execute_query(
            'INSERT INTO encrypted_summoner_ids (name, encrypted_summoner_id) VALUES (?, ?);',
            (player_name, encrypted_summoner_id))
