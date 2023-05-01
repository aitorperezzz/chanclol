import os
import asyncio
import discord
import bot
from dotenv import load_dotenv

# Get discord token from the environment
load_dotenv()
token = os.getenv('DISCORD_TOKEN')
if token == None:
    raise EnvironmentError(
        'DISCORD_TOKEN not found in the environment')

# Create a discord client with the correct intents
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Set up logging of the discord library.
# If not running with client.run(), the library will not produce any output
discord.utils.setup_logging()

# Create the bot
chanclol_bot = bot.Bot()


@client.event
async def on_ready():
    print(f' -> {client.user} has connected to Discord')
    print('Client is connected to the following servers:')
    for guild in client.guilds:
        print(guild)


@client.event
async def on_message(message):
    print(f' -> Forwarding message from {message.author}: {message.content}')
    await chanclol_bot.receive(message, client)


# Function that creates all the tasks in the server
async def spawn_main_tasks():
    # The bot checks the in-game status of all the users registered in an infinite loop
    bot_task = asyncio.create_task(chanclol_bot.loop_check_games())
    # The client listens to messages sent on discord and forwards them to the bot
    client_task = asyncio.create_task(client.start(token))
    # Wait for all tasks to complete (in reality they never will)
    await asyncio.gather(bot_task, client_task)

# Call main function and block here
asyncio.run(spawn_main_tasks())
