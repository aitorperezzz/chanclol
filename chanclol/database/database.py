import logging
import os
import sqlite3

logger = logging.getLogger(__name__)


# Base database class
class Database:

    def __init__(self, filename: str):
        self.filename = filename
        self.initialize()

    # Initializes the database
    def initialize(self):
        pass

    # Decides if the database is already initialized
    # (if the file is present)
    def initialized(self) -> bool:
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
