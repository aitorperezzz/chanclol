import math
import time
import asyncio
import logging

logger = logging.getLogger(__name__)


def get_time_milliseconds():
    return math.floor(time.time() * 1000)


class Restriction:
    # A restriction consists of a number of requests that are allowed
    # in a specified interval. The interval is expressed in milliseconds
    def __init__(self, requests, interval):
        self.requests = requests
        self.interval = interval

    # Decide if a request done at this moment is allowed taking into account
    # the history of transactions
    def allowed(self, history):
        # Compute the number of requests that have been sent in the interval.
        # If strictly smaller than the max allowed, return OK
        current_time = get_time_milliseconds()
        count = 0
        for element in history:
            if (current_time - element) < self.interval:
                count += 1
        return count < self.requests


class RateLimiter:
    # Create a rate limiter with certain restrictions. Then you can use it to know
    # if you're allowed to make a request
    def __init__(self, restrictions):
        self.restrictions = restrictions
        self.history = []
        self.max_interval = -math.inf
        for restriction in self.restrictions:
            if restriction.interval > self.max_interval:
                self.max_interval = restriction.interval

    # Call this function to know if a request is allowed.
    # If allowed, the function will return OK
    # If not allowed but the request is not vital, it will return NOK
    # If not allowed but the request is vital, it will block async until it is allowed
    async def allowed(self, vital):
        while True:
            # Trim history first
            self.trim()
            # Check if restrictions allow this request
            allowed = self.allowed_by_restrictions()
            if allowed:
                self.history.append(get_time_milliseconds())
                logger.debug('Allowing the request')
                return True
            elif not vital:
                logger.warning('Rejecting a non vital request')
                return False
            else:
                logger.warning('Delaying a vital request')
                await asyncio.sleep(1)

    # Trims the history of requests by deleting all the timestamps older than
    # the max interval that all restrictions care about
    def trim(self):
        current_time = get_time_milliseconds()
        self.history = [x for x in self.history if (
            current_time - x) < self.max_interval]

    # Decides if a request is allowed according to all the restrictions
    def allowed_by_restrictions(self):
        allowed = True
        for restriction in self.restrictions:
            allowed = allowed and restriction.allowed(self.history)
        return allowed
