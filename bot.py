import riotapi
import asyncio
import parsing

# The bot contains as many Guild classes as servers have invited
# the bot and interacted with it


class Guild:
    def __init__(self, id, channel):
        # Unique identifier of the guild as handled by discord
        self.id = id
        # Copy of the channel object to send messages to
        self.channel = channel
        # List of usernames registered in this server
        self.usernames = []
        # Bot prefix being used in this server
        self.prefix = 'chanclol'

    # Register a new username in the internal list
    async def register(self, riotapi, username):

        # Check if the username is already in the list
        if username in self.usernames:
            response = f'Username {username} is already registered'
            print(response)
            await self.channel.send(response)
            return

        # Check the username in fact exists
        league_info = riotapi.get_league_info(username)
        if league_info == None:
            response = f'Could not get response from Riot API for user {username}'
            print(response)
            await self.channel.send(response)
            return

        # Now it's safe to add to the list
        self.usernames.append(username)

        # Send a final message
        response = f'User {username} registered correctly'
        print(response)
        response += '\n'
        for league in league_info['response']:
            response += f'Queue {league["queueType"]}: rank {league["tier"]} {league["rank"]} {league["leaguePoints"]} LPs\n'
        await self.channel.send(response)

    # Unregister a username from the internal list
    async def unregister(self, username):
        # Check if the username is already in the list
        if username in self.usernames:
            self.usernames.remove(username)
            response = f'Username {username} unregistered correctly'
        else:
            response = f'Username {username} is not registered'
        print(response)
        await self.channel.send(response)

    # Print the usernames currently registered
    async def print(self):
        if len(self.usernames) == 0:
            response = 'No usernames registered'
        else:
            response = 'Usernames currently registered:\n'
            for username in self.usernames:
                response += f'{username}\n'
        print(response)
        await self.channel.send(response)

    # Changes the prefix in this server
    async def change_prefix(self, new_prefix):
        self.prefix = new_prefix
        response = f'Prefix has been changed to {self.prefix}'
        print(response)
        await self.channel.send(response)


# The bot: receives commands from the discord client
# and processes them. It runs an infinite loop that checks the
# in-game status of all the usernames registered for each guild
class Bot:
    def __init__(self):
        # All the guild-related information managed by the bot
        self.guilds = {}
        # Riot API class
        self.riot_api = riotapi.RiotApi()

    # Main entry point for all messages
    async def receive(self, message, client):
        # Reject my own messages
        if message.author == client.user:
            print('Rejecting message sent by myself')
            return

        # Register a guild in case it does not yet exist
        if not message.guild.id in self.guilds:
            print(f'initialising guild {message.guild.id}')
            self.guilds[message.guild.id] = Guild(
                message.guild.id, message.channel)
        guild = self.guilds[message.guild.id]

        # Parse the input provided and call the appropriate function
        parsed_input = parsing.Parser(message.content, guild.prefix)
        if parsed_input.code == parsing.ParseResult.NOT_BOT_PREFIX:
            print('Rejecting message not intended for the bot')
        elif parsed_input.code != parsing.ParseResult.OK:
            response = f'Input is not valid: {parsed_input.get_error_string()}'
            print(response)
            await message.channel.send(response)
        else:
            print('Command understood')
            if parsed_input.command == parsing.Command.REGISTER:
                await guild.register(self.riot_api, ' '.join(parsed_input.arguments))
            elif parsed_input.command == parsing.Command.UNREGISTER:
                await guild.unregister(' '.join(parsed_input.arguments))
            elif parsed_input.command == parsing.Command.PRINT:
                await guild.print()
            elif parsed_input.command == parsing.Command.PREFIX:
                await guild.change_prefix(parsed_input.arguments[0])
            else:
                raise ValueError('Command is not one of the possible ones')

    async def loop_check_games(self):
        while True:
            for guildid in self.guilds:
                for username in self.guilds[guildid].usernames:
                    # Make a request to Riot and check if the user is in game
                    active_game_info = self.riot_api.get_active_game_info(
                        username)
                    if active_game_info['error']:
                        print(
                            f'Error retrieving in-game data for username {username}')
                    elif not active_game_info['in_game']:
                        print(f'User {username} is currently not playing')
                    else:
                        response = f'User {username} is playing'
                        print(response)
                        asyncio.create_task(
                            self.guilds[guildid].channel.send(response))

            await asyncio.sleep(10)
