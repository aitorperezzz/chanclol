import logging

from database import Database

logger = logging.getLogger(__name__)


# Database used by the Riot API as a cache
class DatabaseRiotApi(Database):

    # Initializes the database
    def initialize(self):

        logger.info("Initialising database")
        if not self.initialized():
            logger.info("Creating tables in database")
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

    # Once the Riot API has downloaded the champions data, it will call this function
    # to store them
    def set_champions(self, champions: dict) -> None:
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
    def get_champions(self) -> dict:

        logger.info("Getting champions from the database")
        query = "SELECT * FROM champions;"
        result = self.execute_query(query)
        champions = {}
        for element in result:
            champions[element[0]] = element[1]
        if len(champions) == 0:
            logger.info("Table champions is currently empty")
        return champions

    # Get all the riot ids as stored in the database
    def get_riot_ids(self) -> dict:

        logger.info("Getting riot ids")
        result = self.execute_query("SELECT * FROM riot_ids;")
        # Convert to a dictionary
        riot_ids = {}
        for element in result:
            riot_ids[element[0]] = (element[1], element[2])
        if len(riot_ids) == 0:
            logger.info("No riot ids present in the database")
        return riot_ids

    # Purges all the names from the database, except some that we need to keep
    def set_riot_ids(self, riot_ids: dict) -> None:

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

    # Add a name to the database
    def add_riot_id(self, puuid: str, riot_id: tuple[str]) -> None:

        logger.info(f"Adding riot id {riot_id} of player {puuid} to the database")
        self.execute_query(
            "INSERT INTO riot_ids (puuid, game_name, tag_line) VALUES (?, ?, ?);",
            (puuid, riot_id[0], riot_id[1]),
        )

    def get_summoner_ids(self) -> dict:

        logger.info("Getting summoner ids")
        result = self.execute_query("SELECT * FROM summoner_ids;")
        # Convert to a dictionary
        summoner_ids = {}
        for element in result:
            summoner_ids[element[0]] = element[1]
        if len(summoner_ids) == 0:
            logger.info("No summoner ids present in the database")
        return summoner_ids

    # Purges all the names from the database, except some that we need to keep
    def set_summoner_ids(self, summoner_ids: dict) -> None:

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

    def add_summoner_id(self, puuid: str, summoner_id: str) -> None:

        logger.info(
            f"Adding summoner id {summoner_id} of player {puuid} to the database"
        )
        self.execute_query(
            "INSERT INTO summoner_ids (puuid, summoner_id) VALUES (?, ?);",
            (puuid, summoner_id),
        )

    # Get the current version of the patch
    def get_version(self) -> str:

        query = "SELECT * FROM version;"
        result = self.execute_query(query)
        if len(result) != 1:
            raise ValueError(
                "Table version in the database needs to contain one and only one value"
            )
        return result[0][0]

    # Update the value of the patch version
    def set_version(self, version: str):

        query = "UPDATE version SET version=?;"
        self.execute_query(query, (version,))
