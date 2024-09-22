import time


# Information about the mastery of a player with a certain champion
class Mastery:

    def __init__(self, level: int, last_play_time: int) -> None:

        self.level = level
        time_in_seconds = time.time()
        self.days_since_last_played = round(
            (time_in_seconds - last_play_time / 1000) / 3600 / 24
        )

    @classmethod
    def create(cls, data: dict | None):

        if not data:
            return None

        # Level
        level = data["championLevel"]
        # Last play time
        last_play_time = data["lastPlayTime"]

        return cls(level, last_play_time)
