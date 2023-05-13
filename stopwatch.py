import time
import math


class StopWatch:
    # This stopwatch keeps track of time. You can set a timeout for it, make it start
    # counting time, and ask it if the timeout has been reached
    def __init__(self, timeout):
        self.timeout = timeout
        self.start_time = -math.inf

    # Set a new timeout
    def set_timeout(self, timeout):
        self.timeout = timeout

    # Start counting time, meaning start time is updated to now
    def start(self):
        self.start_time = math.floor(time.time() * 1000)

    # Return the current start time
    def get_start_time(self):
        return self.start_time

    # Return true if timeout has already passed since start time
    def timeout_reached(self):
        current_time = math.floor(time.time() * 1000)
        return (current_time - self.start_time) > self.timeout
