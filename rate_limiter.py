import math
import time
import asyncio
import logging
import uuid
import functools

logger = logging.getLogger(__name__)


def get_time_milliseconds():
    return math.floor(time.time() * 1000)


class Analysis:
    # Returned by a restriction after performing an analysis of the history
    def __init__(self, allowed, status):
        self.allowed = allowed
        self.status = status


class Restriction:
    # A restriction consists of a number of requests that are allowed
    # in a specified interval. The interval is expressed in milliseconds
    def __init__(self, requests, interval):
        self.requests = requests
        self.interval = interval

    # Decide if a request can be allowed at this moment taking into account
    # the history of transactions
    def perform_analysis(self, history):
        # Compute the number of requests that have been sent in the interval.
        # If strictly smaller than the max allowed, return OK
        current_time = get_time_milliseconds()
        count = 0
        for element in history:
            if (current_time - element) < self.interval:
                count += 1
        return Analysis(count < self.requests, self.status_message(count))

    # Returns a string with the current status of the restriction
    def status_message(self, count):
        return f'{int(self.interval / 1000)} secs, {count} reqs'


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
        # List of pending vital requests
        self.pending_vital_requests = set()

    # Call this function to know if a request is allowed.
    # If allowed, the function will return OK
    # If not allowed but the request is not vital, it will return NOK
    # If not allowed but the request is vital, it will block async until it is allowed
    async def allowed(self, vital):
        # Give this request a unique identifier in case it's needed
        my_uuid = str(uuid.uuid4())
        while True:
            # Trim history first
            self.trim()
            # Check if restrictions allow this request
            analysis_restrictions = self.get_restrictions_analysis()
            allowed = functools.reduce(
                lambda a, b: a.allowed and b.allowed, analysis_restrictions)
            status_message = ' '.join(
                f'[{analysis.status}]' for analysis in analysis_restrictions)
            current_queue_size = len(self.pending_vital_requests)
            if allowed:
                if vital or not vital and current_queue_size == 0:
                    logger.debug('Allowing request')
                    # In this case, allow the request and pop it out of the queue
                    if my_uuid in self.pending_vital_requests:
                        self.pending_vital_requests.remove(my_uuid)
                    # Mark the time of this request in the history
                    self.history.append(get_time_milliseconds())
                    return True
                else:
                    # Non vital and queue is not empty
                    logger.warning(
                        f'Rejecting a non vital request because queue is not empty {status_message} [queue size: {current_queue_size}]')
                    return False
            elif not vital:
                logger.warning(
                    f'Rejecting a non vital request because of restrictions {status_message} [queue size: {current_queue_size}]')
                return False
            else:
                # Add this request to the pending ones if needed
                if not my_uuid in self.pending_vital_requests:
                    self.pending_vital_requests.add(my_uuid)
                logger.warning(
                    f'Delaying a vital request {status_message} [queue size: {current_queue_size}]')
                await asyncio.sleep(1)

    # Trims the history of requests by deleting all the timestamps older than
    # the max interval that all restrictions care about
    def trim(self):
        current_time = get_time_milliseconds()
        self.history = [x for x in self.history if (
            current_time - x) < self.max_interval]

    # Decides if a request is allowed according to all the restrictions
    def get_restrictions_analysis(self):
        analysis = []
        for restriction in self.restrictions:
            analysis.append(restriction.perform_analysis(self.history))
        return analysis
