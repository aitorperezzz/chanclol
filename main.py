import os
import asyncio
import discord
import bot
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import json

# Read the configuration
config = None
with open('config.json') as config_file:
    config = json.load(config_file)

# Set up logging for the complete application with a rotating log
handler = RotatingFileHandler(
    filename=config['log_filename'], mode='w', maxBytes=100 * 1024 * 1024, backupCount=10)
discord.utils.setup_logging(handler=handler)
level = logging.getLevelName(config['log_level'])
logging.getLogger().setLevel(level)

logger = logging.getLogger(__name__)

# Load env variables
load_dotenv()
riot_api_key = os.getenv('RIOT_API_KEY')
if riot_api_key == None:
    raise ValueError(
        'RIOT_API_KEY has not been found in the environment')
discord_token = os.getenv('DISCORD_TOKEN')
if discord_token == None:
    raise ValueError(
        'DISCORD_TOKEN has not been found in the environment')

# Create a discord client with the correct intents
intents = discord.Intents.default()
intents.message_content = True
activity = discord.Activity(
    type=discord.ActivityType.listening, name="chanclol help")
client = discord.Client(intents=intents, activity=activity)


# Create the bot
chanclol_bot = bot.Bot(client, riot_api_key, config)


@client.event
async def on_ready():
    logger.info(f'{client.user} has connected to Discord')
    logger.info(
        f'Client is connected to the following servers: {", ".join([str(guild) for guild in client.guilds])}')


@client.event
async def on_message(message):
    logger.debug(
        f'Forwarding message from {message.author}: {message.content}')
    await chanclol_bot.receive(message)


# Function that creates all the tasks in the server
async def spawn_main_tasks():
    # The bot checks the in-game status of all the users registered in an infinite loop
    bot_task = asyncio.create_task(chanclol_bot.loop_check_games())
    # The client listens to messages sent on discord and forwards them to the bot
    client_task = asyncio.create_task(client.start(discord_token))
    # Wait for all tasks to complete (in reality they never will)
    await asyncio.gather(bot_task, client_task)

# Call main function and block here
asyncio.run(spawn_main_tasks())
