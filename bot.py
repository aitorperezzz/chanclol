import riotapi


class Bot:
    def __init__(self):
        # The prefix used by the bot
        self.prefix = 'chanclol'
        # Internal list of usernames that the bot handles
        self.username_list = []
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
            return
        command = words[0]
        if command == 'register':
            await self.register(message, words[1:])
        elif command == 'print':
            await self.print(message)
        elif command == 'unregister':
            await self.unregister(message, words[1:])
        else:
            response = f'Command {command} is not understood'
            print(response)
            await message.channel.send(response)

        print('Message has been processed')

    async def register(self, message, words):
        # chanclol register <username>
        if len(words) != 1:
            print(f'Register command called with words: "{words}"')
            await message.channel.send('register command accepts only one word: a Riot username')
            return
        username = words[0]

        # Check if the username is already in the list
        if username in self.username_list:
            response = f'Username {username} is already registered'
            print(response)
            await message.channel.send(response)
            return

        # Check the username in fact exists
        league_info = self.riot_api.get_league_info(username)
        if league_info == None:
            response = f'Could not get response from Riot API for user {username}'
            print(response)
            await message.channel.send(response)
            return

        # Now it's safe to add to the list
        self.username_list.append(username)

        # Send a final message
        response = f'User {username} registered correctly'
        print(response)
        response += '\n'
        for league in league_info:
            response += f'Queue {league["queueType"]}: rank {league["tier"]} {league["rank"]} {league["leaguePoints"]} LPs\n'
        await message.channel.send(response)

    async def print(self, message):
        response = 'Riot usernames currently registered:\n'
        for username in self.username_list:
            response += f'{username}\n'
        await message.channel.send(response)

    def unregister(self, message, words):
        raise NotImplemented()
