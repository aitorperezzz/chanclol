import math
import time

from stopwatch import StopWatch


# A unique player registered by the bot
class Player:

    def __init__(self, id: str):

        # Unique identifier of the player
        self.id = id
        # Create a stopwatch that will keep track of the last time the in game status was checked
        # for this player
        self.stopwatch = StopWatch()
        # Last time the player was seen online
        self.last_online_secs = -math.inf

    # Updates the internal stopwatch of the player according to the online status and the time elapsed
    # Return True if the timeout has actually been changed, False if not
    def update_check_timeout(
        self,
        online: bool,
        offline_threshold_mins: int,
        timeout_online_secs: int,
        timeout_offline_secs: int,
    ) -> bool:

        current_time = time.time()
        # If the player is currently online, set the timeout to online
        if online:
            self.last_online_secs = current_time
            if self.stopwatch.get_timeout() != timeout_online_secs * 1000:
                self.stopwatch.set_timeout(timeout_online_secs * 1000)
                return True
        # If not online, we need to know how long the player has been offline
        else:
            if current_time - self.last_online_secs > offline_threshold_mins * 60:
                if self.stopwatch.get_timeout() != timeout_offline_secs * 1000:
                    self.stopwatch.set_timeout(timeout_offline_secs * 1000)
                    return True
        return False
