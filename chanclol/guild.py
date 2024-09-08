# Any guild where this bot has been invited
class Guild:

    def __init__(self, id: int, channel_id: int):

        # Unique identifier of the guild
        self.id: int = id
        # Unique identifier of the channel where the bot will send in-game messages
        self.channel_id: int = channel_id
        # Players registered in this guild together with the game id
        # that was last informed for them in this guild
        self.last_informed_game_ids: dict[str, int | None] = {}
