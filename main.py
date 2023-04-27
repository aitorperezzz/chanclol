import os
import discord
import bot
from dotenv import load_dotenv

# Get discord token from the environment
load_dotenv()
token = os.getenv('DISCORD_TOKEN')
if token == None:
    raise EnvironmentError(
        'DISCORD_TOKEN not found in the environment')

# Create a client and a bot
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
bot = bot.Bot()


@client.event
async def on_ready():
    print(f' -> {client.user} has connected to Discord')
    print('Client is connected to the following servers:')
    for guild in client.guilds:
        print(guild)


@client.event
async def on_message(message):
    print(f' -> Forwarding message from {message.author}: {message.content}')
    await bot.receive(message, client)


client.run(token)
