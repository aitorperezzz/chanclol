# Any guild where this bot has been invited
class Guild:

    def __init__(self, id: str, channel_id: str):

        # Unique identifier of the guild
        self.id = id
        # Unique identifier of the channel where the bot will send in-game messages
        self.channel_id = channel_id
        # Players registered in this guild together with the game id
        # that was last informed for them in this guild
        self.last_informed_game_ids = {}
