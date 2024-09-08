import logging
import aiohttp
from enum import Enum

import rate_limiter

logger = logging.getLogger(__name__)


# Responses provided by the Riot API
class ResponseStatus(Enum):
    OK = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    DATA_NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    UNSUPPORTED_MEDIA_TYPE = 415
    RATE_LIMIT_EXCEEDED = 429
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504


messages = {
    ResponseStatus.OK: "OK",
    ResponseStatus.BAD_REQUEST: "Bad request",
    ResponseStatus.UNAUTHORIZED: "Unauthorized",
    ResponseStatus.FORBIDDEN: "Forbidden",
    ResponseStatus.DATA_NOT_FOUND: "Data not found",
    ResponseStatus.METHOD_NOT_ALLOWED: "Method not allowed",
    ResponseStatus.UNSUPPORTED_MEDIA_TYPE: "Unsupported media type",
    ResponseStatus.RATE_LIMIT_EXCEEDED: "Rate limit exceeded",
    ResponseStatus.INTERNAL_SERVER_ERROR: "Internal server error",
    ResponseStatus.BAD_GATEWAY: "Bad gateway",
    ResponseStatus.SERVICE_UNAVAILABLE: "Service unavailable",
    ResponseStatus.GATEWAY_TIMEOUT: "Gateway timeout",
}


class Proxy:
    def __init__(self, api_key, restrictions):
        self.rate_limiter = rate_limiter.RateLimiter(restrictions)
        self.api_key = api_key

    # Make a simple async request
    async def request(self, url, vital):

        # Wait until the request can be made
        allowed = await self.rate_limiter.allowed(vital)
        if not allowed:
            logger.warning("Rate limiter is not allowing the request")
            return None

        # Make the request and check the response status
        logger.debug(f"Making a request to url {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._build_api_header()) as r:
                return await self._create_response(r)

    # Return a header that includes the API key
    def _build_api_header(self):
        if self.api_key == None:
            logger.error("API key is not available")
            return None
        return {"X-Riot-Token": self.api_key}

    # Create an internal response with the aiohttp response, logging in the
    # process the relevant status codes for this application
    async def _create_response(self, response):

        if not response:
            return None

        # Log accorging to the status
        message = messages[ResponseStatus(response.status)]
        match ResponseStatus(response.status):
            case ResponseStatus.OK | ResponseStatus.DATA_NOT_FOUND:
                logger.debug(message)
            case ResponseStatus.RATE_LIMIT_EXCEEDED:
                logger.warning(message)
                self.rate_limiter.received_rate_limit()
            case _:
                logger.error(message)

        match ResponseStatus(response.status):
            case ResponseStatus.OK:
                return await response.json()
            case _:
                return None
