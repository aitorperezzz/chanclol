# chanclol

Discord bot written in Go to retrieve live data before a League of Legends game starts.

## How to use it

After the bot has been invited to your server, it will:

- List all the commands available and their usage when typing `chanclol help`
- Accept your requests to register new players identified through a riot id, which has the form `<game_name>#<tag_line>`. For every player registered, the bot will cyclically check if the player is online. If so, it will send a message to your server with information of every player of every team in their current game: their mastery with the champion they are playing, and their current rank (if any)
- Unregister a player to stop receiving live messages
- Change the channel on which the bot sends its live messages
- Print the status of the server: the players that are registered, and the channel being used to send live messages

## How to run it

First prepare a `.env` file defining the following two environment variables:

- `RIOT_API_KEY`: valid API key as provided by Riot
- `DISCORD_TOKEN`: the token necessary to connect to Discord

It is recommended to run the application in a container. To do so, run `docker compose build` to build the Docker image, and then `docker compose up -d` to start a container and then detach from it.

You can also run the application locally. To do so, `go` needs to be installed. Install the dependencies, compile, and run.
