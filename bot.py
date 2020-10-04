# bot.py
import os

import discord
from dotenv import load_dotenv

SERVER_NAME = "Hermanas Místicas"

def getToken():
	try:
		f = open("discordToken.txt", "r")
		lineas = f.read()
		f.close()
		return lineas
	except:
		print("ERROR: No se encontró el TOKEN para conectar con Discord")
		return None


DISCORD_TOKEN = getToken()
DISCORD_GUILD = SERVER_NAME
client = discord.Client()

@client.event
async def on_ready():
	print(f'{client.user} has connected to Discord!')

client.run(DISCORD_TOKEN)