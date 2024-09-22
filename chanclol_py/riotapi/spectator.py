import logging

from riotapi.participant import Participant
from riotapi.riotapi import RiotApi

logger = logging.getLogger(__name__)


# Information about a live game
class Spectator:

    def __init__(
        self,
        game_id: int,
        game_mode: str,
        game_length_mins: int,
        teams: dict[int, list[Participant]],
    ) -> None:

        self.game_id = game_id
        self.game_mode = game_mode
        self.game_length_mins = game_length_mins
        self.teams = teams

    @classmethod
    async def create(cls, data: dict | None, riot_api: RiotApi):

        if not data:
            return None

        # Game id
        game_id = data["gameId"]
        # Game mode
        game_mode = data["gameMode"]
        # Game length
        game_length_mins = round(data["gameLength"] / 60)
        # Create the list of all the provided team ids
        team_ids = list(
            set([participant["teamId"] for participant in data["participants"]])
        )
        # Fill in the teams
        teams: dict[int, list[Participant]] = {}
        for team_id in team_ids:
            teams[team_id] = []
            for participant_data in data["participants"]:
                if participant_data["teamId"] == team_id:
                    participant = await Participant.create(participant_data, riot_api)
                    if not participant:
                        logger.error(
                            f"Could not create participant while preparing spectator data"
                        )
                        return None
                    teams[team_id].append(participant)

        return cls(game_id, game_mode, game_length_mins, teams)
