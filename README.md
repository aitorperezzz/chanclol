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

First prepare a `.env` file defining the following environment variables:

- `RIOT_API_KEY`: valid API key as provided by Riot
- `DISCORD_TOKEN`: the token necessary to connect to Discord

It is recommended to run the application in a container:

```sh
docker compose build
docker compose up -d
```

By default, Docker Compose uses the local image name `chanclol:latest`. To run a specific image, override it with the `IMAGE` environment variable:

```sh
IMAGE=registry.example.com/chanclol:latest docker compose up -d
```

You can also run the application locally with Go installed:

```sh
go test ./...
go run .
```

By default, local runs read `config.json` and store the bot database files in the current directory.

## Container image

The Docker image is built with a Go builder stage, runs the test suite during the build, and copies only the compiled static binary plus `config.json` into the final image.

The GitLab pipeline uses Buildah and pushes two tags to the GitLab container registry when `main` is built:

- `$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA`
- `$CI_REGISTRY_IMAGE:latest`
