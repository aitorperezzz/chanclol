from stopwatch import StopWatch


class TimedExecutor:
    # Gets called from time to time on execute. When the timer is done, will
    # await the coroutine provided
    def __init__(self, timeout, task):
        self.stopwatch = StopWatch()
        self.stopwatch.set_timeout(timeout)
        self.task = task
        self.stopwatch.start()

    async def execute(self):
        if self.stopwatch.time_behind() > 0:
            self.stopwatch.start()
            await self.task()
