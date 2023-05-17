import time
import math


class StopWatch:
    # This stopwatch keeps track of time. You can set a timeout for it, make it start
    # counting time, and ask it if the timeout has been reached
    # Timeout needs to be provided in milliseconds
    def __init__(self):
        self.timeout = None
        self.start_time = -math.inf

    # Get the current timeout in milliseconds
    def get_timeout(self):
        return self.timeout

    # Set a new timeout in milliseconds
    def set_timeout(self, timeout):
        self.timeout = timeout

    # Start counting time, meaning start time is updated to now
    def start(self):
        self.start_time = math.floor(time.time() * 1000)

    # Return the current start time
    def get_start_time(self):
        return self.start_time

    # Return the number of milliseconds that have passed since the timeout was reached.
    # Naturally, if the number is negative, the timeout has not been reached
    def time_behind(self):
        current_time = math.floor(time.time() * 1000)
        return (current_time - self.start_time) - self.timeout
