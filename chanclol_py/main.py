import os
import asyncio
import discord
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import json

from bot import Bot

# Read the configuration
config = None
with open("config.json") as config_file:
    config = json.load(config_file)

# Set up logging for the complete application
# Rotating file
discord.utils.setup_logging(
    handler=RotatingFileHandler(
        filename=config["log_filename"],
        mode="w",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
    )
)
# Console
discord.utils.setup_logging(handler=logging.StreamHandler())
# Level
level = logging.getLevelNamesMapping()[config["log_level"]]
logging.getLogger().setLevel(level)

logger = logging.getLogger(__name__)

# Load env variables
# (From the documentation: "By default, load_dotenv doesn't override existing environment variables.")
load_dotenv(override=True)
riotapi_key = os.getenv("RIOT_API_KEY")
if riotapi_key == None:
    raise ValueError("RIOT_API_KEY has not been found in the environment")
discord_token = os.getenv("DISCORD_TOKEN")
if discord_token == None:
    raise ValueError("DISCORD_TOKEN has not been found in the environment")

# Create a discord client with the correct intents
intents = discord.Intents.default()
intents.message_content = True
activity = discord.Activity(type=discord.ActivityType.listening, name="chanclol help")
client = discord.Client(intents=intents, activity=activity)

# Read all the configuration needed by the bot
database_filename_bot = config["database_filename_bot"]
database_filename_riotapi = config["database_filename_riotapi"]
offline_threshold_mins = config["offline_threshold_mins"]
timeout_online_secs = config["timeout_online_secs"]
timeout_offline_secs = config["timeout_offline_secs"]
main_loop_cycle_secs = config["main_loop_cycle_secs"]
riotapi_housekeeping_cycle_hrs = config["riotapi_housekeeping_cycle_hrs"]
restrictions = config["restrictions"]
# Create the bot
chanclol_bot = Bot(
    client,
    database_filename_bot,
    offline_threshold_mins,
    timeout_online_secs,
    timeout_offline_secs,
    main_loop_cycle_secs,
    riotapi_housekeeping_cycle_hrs,
    riotapi_key,
    database_filename_riotapi,
    restrictions,
)


@client.event
async def on_ready():
    logger.info(f"{client.user} has connected to Discord")
    logger.info(
        f'Client is connected to the following servers: {", ".join([str(guild) for guild in client.guilds])}'
    )


@client.event
async def on_message(message):
    logger.debug(f"Forwarding message from {message.author}: {message.content}")
    await chanclol_bot.receive(message)


# Function that creates all the tasks in the server
async def spawn_main_tasks():
    # The bot checks the in-game status of all the users registered in an infinite loop
    bot_task = asyncio.create_task(chanclol_bot.loop())
    # The client listens to messages sent on discord and forwards them to the bot
    client_task = asyncio.create_task(client.start(discord_token))
    # Wait for all tasks to complete (in reality they never will)
    await asyncio.gather(bot_task, client_task)


# Call main function and block here
asyncio.run(spawn_main_tasks())
