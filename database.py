import sqlite3
import os


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
                PRIMARY KEY ('name'));"""
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
                'player_name' VARCHAR(256) NOT NULL DEFAULT '',
                'encrypted_summoner_id' VARCHAR(256) NOT NULL DEFAULT '',
                PRIMARY KEY ('player_name'));"""
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
                """INSERT INTO champions (id, name) VALUES (?, ?);""", (id, champions[id],))

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
                """INSERT INTO spells (id, name) VALUES (?, ?);""", (id, spells[id],))

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
