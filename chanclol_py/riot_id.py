class RiotId:

    def __init__(self, game_name: str, tag_line: str):

        self.game_name: str = game_name
        self.tag_line: str = tag_line

    def __str__(self) -> str:
        return f"{self.game_name}#{self.tag_line}"

    def __eq__(self, other) -> bool:
        if isinstance(other, self.__class__):
            return self.game_name == other.game_name and self.tag_line == other.tag_line
        else:
            return False
