import logging

logger = logging.getLogger(__name__)


# Information returned, for a specific player and for a specific
# queue, containing its current ranked position in that queue
class League:

    def __init__(
        self, queue_type: str, tier: str, rank: str, lps: int, wins: int, losses: int
    ):

        self.queue_type = queue_type
        self.tier = tier
        self.rank = rank
        self.lps = lps
        self.wins = wins
        self.losses = losses
        total_games = self.wins + self.losses
        self.win_rate = int(self.wins / (total_games) * 100) if total_games != 0 else 0

    @classmethod
    def create(cls, data: dict | None, queue_type):

        if not data:
            return None

        # Tier
        tier = data["tier"]
        # Rank
        rank = data["rank"]
        # LPs
        lps = data["leaguePoints"]
        # Wins
        wins = data["wins"]
        # Losses
        losses = data["losses"]

        return cls(queue_type, tier, rank, lps, wins, losses)
