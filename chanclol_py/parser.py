from enum import Enum, auto
import logging

logger = logging.getLogger(__name__)

PREFIX = "chanclol"


# Commands supported by the bot
class Command(Enum):
    REGISTER = auto()
    UNREGISTER = auto()
    PRINT = auto()
    CHANNEL = auto()
    HELP = auto()
    RANK = auto()


# Possible results after parsing user input
# from a syntax point of view
class Result(Enum):
    OK = auto()
    NO_BOT_PREFIX = auto()
    NO_COMMAND = auto()
    COMMAND_NOT_RECOGNISED = auto()
    NO_INPUT = auto()
    NOT_A_RIOT_ID = auto()


ERROR_MESSAGES = {
    Result.NO_COMMAND: "No command provided",
    Result.COMMAND_NOT_RECOGNISED: "Command `{command}` not recognised",
    Result.NO_INPUT: "Command `{command}` requires an argument",
    Result.NOT_A_RIOT_ID: "Input `{word}` is not a riot id",
}


class Parser:

    def __init__(self, message):

        self.result: Result | None = None
        self.error_message: str | None = None
        self.command: Command | None = None
        self.arguments: list[str] = []
        self.parse(message)

    def parse_riot_id(self, words: list[str]) -> None:

        word = "".join(words)
        hashtag_pos = word.find("#")
        if hashtag_pos == -1:
            self.code = Result.NOT_A_RIOT_ID
            self.error_message = ERROR_MESSAGES[Result.NOT_A_RIOT_ID].format(word=word)
        else:
            self.code = Result.OK
            game_name = word[:hashtag_pos]
            tag_line = word[hashtag_pos + 1 :]
            self.arguments = [game_name, tag_line]

    def parse(self, message: str):

        # The message has to start with the bot prefix
        if not message.startswith(PREFIX):
            logger.debug("Rejecting message not intended for the bot")
            self.code = Result.NO_BOT_PREFIX
            return

        # Get the command if it exists
        words = message[len(PREFIX) :].strip(" \n\t").split()
        if len(words) == 0:
            self.code = Result.NO_COMMAND
            self.error_message = ERROR_MESSAGES[self.code]
            return
        command = words[0]
        words = words[1:]

        # Match each of the commands
        match command:
            case "register":
                # chanclol register <riot_id>
                self.command = Command.REGISTER
                if len(words) == 0:
                    self.code = Result.NO_INPUT
                    self.error_message = ERROR_MESSAGES[self.code].format(
                        command=command
                    )
                else:
                    self.parse_riot_id(words)
            case "unregister":
                # chanclol unregister <riot_id>
                self.command = Command.UNREGISTER
                if len(words) == 0:
                    self.code = Result.NO_INPUT
                    self.error_message = ERROR_MESSAGES[self.code].format(
                        command=command
                    )
                else:
                    self.parse_riot_id(words)
            case "print":
                # chanclol print
                self.command = Command.PRINT
                self.code = Result.OK
            case "channel":
                # chanclol channel <channel_name>
                self.command = Command.CHANNEL
                if len(words) == 0:
                    self.code = Result.NO_INPUT
                    self.error_message = ERROR_MESSAGES[self.code].format(
                        command=command
                    )
                else:
                    self.code = Result.OK
                    self.arguments = [" ".join(words)]
            case "help":
                # chanclol help
                self.command = Command.HELP
                self.code = Result.OK
            case "rank":
                # chanclol rank <riot_id>
                self.command = Command.RANK
                if len(words) == 0:
                    self.code = Result.NO_INPUT
                    self.error_message = ERROR_MESSAGES[self.code].format(
                        command=command
                    )
                else:
                    self.parse_riot_id(words)
            case _:
                self.code = Result.COMMAND_NOT_RECOGNISED
                self.error_message = ERROR_MESSAGES[self.code].format(command=command)
