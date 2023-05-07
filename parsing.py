from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Command(Enum):
    # Commands supported by the bot
    REGISTER = 0
    UNREGISTER = 1
    PRINT = 2
    CHANNEL = 3
    HELP = 4


class ParseResult(Enum):
    # Possible results after parsing user input
    # from a syntax point of view
    OK = 0
    NOT_BOT_PREFIX = 1,
    NO_COMMAND = 2
    COMMAND_NOT_UNDERSTOOD = 3
    REGISTER_NO_INPUT = 4
    UNREGISTER_NO_INPUT = 5
    CHANNEL_NO_INPUT = 6


class Parser():
    def __init__(self, message):
        self.code = None
        self.command = None
        self.arguments = None
        self.prefix = 'chanclol'
        self.parse(message)

    def get_error_string(self):
        if self.code == ParseResult.NO_COMMAND:
            return 'No command provided'
        elif self.code == ParseResult.COMMAND_NOT_UNDERSTOOD:
            return 'Command not recognised'
        elif self.code == ParseResult.REGISTER_NO_INPUT:
            return 'Command `register` requires an argument'
        elif self.code == ParseResult.UNREGISTER_NO_INPUT:
            return 'Command `unregister` requires an argument'
        elif self.code == ParseResult.CHANNEL_NO_INPUT:
            return 'Command `channel` requires an argument'
        else:
            raise ValueError(
                'ParsedInput.get_error_string() called with bad code')

    def parse(self, message):
        if not message.startswith(self.prefix):
            logger.debug('Rejecting message not intended for the bot')
            self.code = ParseResult.NOT_BOT_PREFIX
            return

        # Get the command if it exists
        words = message[len(self.prefix):].strip(' \n\t').split()
        if len(words) == 0:
            self.code = ParseResult.NO_COMMAND
            return
        command = words[0]
        words = words[1:]

        # Check the correct command
        if command == 'register':
            # chanclol register <username>
            self.command = Command.REGISTER
            if len(words) == 0:
                self.code = ParseResult.REGISTER_NO_INPUT
            else:
                self.code = ParseResult.OK
                self.arguments = words
        elif command == 'unregister':
            # chanclol unregister <username>
            self.command = Command.UNREGISTER
            if len(words) == 0:
                self.code = ParseResult.UNREGISTER_NO_INPUT
            else:
                self.code = ParseResult.OK
                self.arguments = words
        elif command == 'print':
            # chanclol print
            self.command = Command.PRINT
            self.code = ParseResult.OK
        elif command == 'channel':
            # chanclol channel <new_channel>
            self.command = Command.CHANNEL
            if len(words) == 0:
                self.code = ParseResult.CHANNEL_NO_INPUT
            else:
                self.code = ParseResult.OK
                self.arguments = words
        elif command == 'help':
            # chanclol help
            self.command = Command.HELP
            self.code = ParseResult.OK
        else:
            self.code = ParseResult.COMMAND_NOT_UNDERSTOOD
