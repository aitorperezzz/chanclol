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
class ParseResult(Enum):
    OK = auto()
    NO_BOT_PREFIX = auto()
    NO_COMMAND = auto()
    COMMAND_NOT_RECOGNISED = auto()
    NO_INPUT = auto()
    NOT_A_RIOT_ID = auto()


error_messages = {
    ParseResult.NO_COMMAND: "No command provided",
    ParseResult.COMMAND_NOT_RECOGNISED: "Command '{command}' not recognised",
    ParseResult.NO_INPUT: "Command '{command}' requires an argument",
    ParseResult.NOT_A_RIOT_ID: "Input '{word}' is not a riot id",
}


class Parser:
    def __init__(self, message):
        self.code = None
        self.message = None
        self.command = None
        self.arguments = None
        self.parse(message)

    def parse_riot_id(self, words):

        word = "".join(words)
        hashtag_pos = word.find("#")
        if hashtag_pos == -1:
            self.code = ParseResult.NOT_A_RIOT_ID
            self.message = error_messages[ParseResult.NOT_A_RIOT_ID].format(word=word)
        else:
            self.code = ParseResult.OK
            game_name = word[:hashtag_pos]
            tag_line = word[hashtag_pos + 1 :]
            self.arguments = (game_name, tag_line)

    def parse(self, message):

        # The message has to start with the bot prefix
        if not message.startswith(PREFIX):
            logger.debug("Rejecting message not intended for the bot")
            self.code = ParseResult.NO_BOT_PREFIX
            return

        # Get the command if it exists
        words = message[len(PREFIX) :].strip(" \n\t").split()
        if len(words) == 0:
            self.code = ParseResult.NO_COMMAND
            self.message = error_messages[self.code]
            return
        command = words[0]
        words = words[1:]

        # Match each of the commands
        match command:
            case "register":
                # chanclol register <riot_id>
                self.command = Command.REGISTER
                if len(words) == 0:
                    self.code = ParseResult.NO_INPUT
                    self.message = error_messages[self.code].format(command=command)
                else:
                    self.parse_riot_id(words)
            case "unregister":
                # chanclol unregister <riot_id>
                self.command = Command.UNREGISTER
                if len(words) == 0:
                    self.code = ParseResult.NO_INPUT
                    self.message = error_messages[self.code].format(command=command)
                else:
                    self.parse_riot_id(words)
            case "print":
                # chanclol print
                self.command = Command.PRINT
                self.code = ParseResult.OK
            case "channel":
                # chanclol channel <channel_name>
                self.command = Command.CHANNEL
                if len(words) == 0:
                    self.code = ParseResult.NO_INPUT
                    self.message = error_messages[self.code].format(command=command)
                else:
                    self.code = ParseResult.OK
                    self.arguments = " ".join(words)
            case "help":
                # chanclol help
                self.command = Command.HELP
                self.code = ParseResult.OK
            case "rank":
                # chanclol rank <riot_id>
                self.command = Command.RANK
                if len(words) == 0:
                    self.code = ParseResult.NO_INPUT
                    self.message = error_messages[self.code].format(command=command)
                else:
                    self.parse_riot_id(words)
            case _:
                self.code = ParseResult.COMMAND_NOT_RECOGNISED
