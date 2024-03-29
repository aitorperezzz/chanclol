import math
import time
import asyncio
import logging
import uuid
import functools
from stopwatch import StopWatch

logger = logging.getLogger(__name__)


def get_time_milliseconds():
    return math.floor(time.time() * 1000)


class Analysis:
    # Returned by a restriction after performing an analysis of the history
    def __init__(self, allowed, status, wait_time):
        self.allowed = allowed
        self.status = status
        self.wait_time = wait_time


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
        # If strictly smaller than the allowed number of requests, it will be allowed.
        # Else it won't, and a wait time in milliseconds will be computed
        current_time = get_time_milliseconds()
        oldest_request = math.inf
        count = 0
        for element in history:
            if (current_time - element) < self.interval:
                # If this request is inside the interval, count it and check if older than the oldest
                count += 1
                if element < oldest_request:
                    oldest_request = element
        if count < self.requests:
            wait_time = 0
        else:
            wait_time = oldest_request - (current_time - self.interval)
        return Analysis(count < self.requests, self.status_message(count), wait_time)

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
        # Stopwatch for the times where riot actively limits requests
        self.stopwatch = StopWatch()
        self.stopwatch.set_timeout(self.max_interval)

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
            analysis = self.get_restrictions_analysis()
            current_queue_size = len(self.pending_vital_requests)
            if analysis.allowed:
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
                        f'Rejecting a non vital request because queue is not empty {analysis.status} [queue size: {current_queue_size}]')
                    return False
            elif not vital:
                logger.warning(
                    f'Rejecting a non vital request {analysis.status} [queue size: {current_queue_size}]')
                return False
            else:
                # Add this request to the pending ones if needed
                if not my_uuid in self.pending_vital_requests:
                    self.pending_vital_requests.add(my_uuid)
                logger.warning(
                    f'Delaying a vital request {int(analysis.wait_time / 1000)} seconds {analysis.status} [queue size: {current_queue_size}]')
                await asyncio.sleep(analysis.wait_time / 1000)

    # Trims the history of requests by deleting all the timestamps older than
    # the max interval that all restrictions care about
    def trim(self):
        current_time = get_time_milliseconds()
        self.history = [x for x in self.history if (
            current_time - x) < self.max_interval]

    # Decides if a request is allowed according to all the restrictions
    def get_restrictions_analysis(self):
        analysis_list = []
        for restriction in self.restrictions:
            analysis_list.append(restriction.perform_analysis(self.history))
        # Merge the received analysis
        allowed = functools.reduce(
            lambda a, b: a.allowed and b.allowed, analysis_list)
        status = ' '.join(
            f'[{analysis.status}]' for analysis in analysis_list)
        wait_time = max([analysis.wait_time for analysis in analysis_list])
        # If the rate limiting stopwatch is running we will need to wait in any case
        if self.stopwatch.get_is_running():
            time_behind = self.stopwatch.time_behind()
            if time_behind > 0:
                # The timeout has been completed, so stop the stopwatch
                self.stopwatch.stop()
            else:
                # The timeout is active, we need to wait until the timeout is reached
                wait_time = abs(time_behind)
                allowed = False
        return Analysis(allowed, status, wait_time)

    # The riot API has responded that I am being rate limited. In this case, probably the rate limiter
    # does not have a good history of requests, so to be safe we should timeout requests during max interval
    def received_rate_limit(self):
        self.stopwatch.start()
