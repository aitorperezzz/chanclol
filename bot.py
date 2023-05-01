import riotapi
import asyncio


class Guild:
    def __init__(self, channel):
        self.channel = channel
        self.usernames = []

    def add_username(self, username):
        self.usernames.append(username)


class Bot:
    def __init__(self):
        # The prefix used by the bot
        self.prefix = 'chanclol'
        # All the guild-related information managed by the bot
        self.guilds = {}
        # Create a Riot API class
        self.riot_api = riotapi.RiotApi()

    # Main entry point for all messages
    async def receive(self, message, client):
        # Reject my own messages
        if message.author == client.user:
            print('Rejecting message sent by myself')
            return

        # Check the message is intended for the bot
        if not message.content.startswith(self.prefix):
            print('Rejecting message not intended for the bot')
            return

        # Decide on the command and call the appropriate function
        words = message.content[len(self.prefix):].strip(' \n\t').split()
        if len(words) == 0:
            print(f'No words to process in message {message}')
            await message.channel.send('Please provide a command')
            return
        command = words[0]
        words = words[1:]
        if command == 'register':
            # chanclol register <username>
            if len(words) != 1:
                print(f'"register" command called with words: "{words}"')
                await message.channel.send('"register" command accepts only one word: a Riot username')
                return
            await self.register(message.channel, message.guild, words[0])
        elif command == 'print':
            # chanclol print
            await self.print(message.channel, message.guild)
        elif command == 'unregister':
            # chanclol unregister <username>
            if len(words) != 1:
                print(f'"unregister" command called with words: "{words}"')
                await message.channel.send('"unregister" command accepts only one word: a Riot username')
                return
            await self.unregister(message.channel, message.guild, words[0])
        else:
            response = f'Command "{command}" is not understood'
            print(response)
            await message.channel.send(response)

        print('Message has been processed')

    async def register(self, channel, guild, username):

        # Add guild if not yet in the dictionary
        if not guild.id in self.guilds:
            self.guilds[guild.id] = Guild(channel)

        # Check if the username is already in the list
        if username in self.guilds[guild.id].usernames:
            response = f'Username {username} is already registered'
            print(response)
            await channel.send(response)
            return

        # Check the username in fact exists
        league_info = self.riot_api.get_league_info(username)
        if league_info == None:
            response = f'Could not get response from Riot API for user {username}'
            print(response)
            await channel.send(response)
            return

        # Now it's safe to add to the list
        self.guilds[guild.id].add_username(username)

        # Send a final message
        response = f'User {username} registered correctly'
        print(response)
        response += '\n'
        for league in league_info['response']:
            response += f'Queue {league["queueType"]}: rank {league["tier"]} {league["rank"]} {league["leaguePoints"]} LPs\n'
        await channel.send(response)

    async def print(self, channel, guild):
        if not guild.id in self.guilds or guild.id in self.guilds and len(self.guilds[guild.id].usernames) == 0:
            response = 'No usernames registered'
            print(response)
            await channel.send(response)
        else:
            response = 'Usernames currently registered:\n'
            for username in self.guilds[guild.id].usernames:
                response += f'{username}\n'
            print(response)
            await channel.send(response)

    def unregister(self, message, words):
        raise NotImplemented()

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
