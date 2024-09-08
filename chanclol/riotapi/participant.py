import logging

import riotapi.riotapi
from riot_id import RiotId
from riotapi.mastery import Mastery
from riotapi.league import League

logger = logging.getLogger(__name__)


# Information about a participant in a spectator (live) game
class Participant:

    def __init__(
        self,
        puuid: str,
        riot_id: RiotId,
        champion_name: str,
        mastery: Mastery | None,
        leagues: list[League],
    ) -> None:

        self.puuid = puuid
        self.riot_id = riot_id
        self.champion_name = champion_name
        self.mastery = mastery
        self.leagues = leagues

    @classmethod
    async def create(cls, data: dict | None, riot_api: riotapi.riotapi.RiotApi):

        if not data:
            return None

        # puuid
        puuid = data["puuid"]
        # riot id
        riot_id = await riot_api.get_riot_id(puuid)
        if not riot_id:
            logger.error(f"Could not find riot id of participant with puuid {puuid}")
            return None
        # Champion name
        champion_id = data["championId"]
        champion_name = await riot_api.get_champion_name(champion_id)
        if not champion_name:
            return None
        # Champion mastery
        mastery = await riot_api.get_mastery(puuid, champion_id)
        # League
        league = await riot_api.get_leagues(puuid)

        return cls(puuid, riot_id, champion_name, mastery, league)
