package bot

import (
	"chanclol/internal/riotapi"
	"fmt"
	"strings"

	"github.com/rs/zerolog/log"
)

const prefix string = "chanclol"

const (
	COMMAND_REGISTER   = iota
	COMMAND_UNREGISTER = iota
	COMMAND_RANK       = iota
	COMMAND_CHANNEL    = iota
	COMMAND_STATUS     = iota
	COMMAND_HELP       = iota
)

const (
	PARSEID_OK                     = iota
	PARSEID_NO_BOT_PREFIX          = iota
	PARSEID_NO_COMMAND             = iota
	PARSEID_COMMAND_NOT_RECOGNISED = iota
	PARSEID_NO_INPUT               = iota
	PARSEID_NOT_A_RIOT_ID          = iota
)

var errorMessages map[int]string = map[int]string{
	PARSEID_NO_COMMAND:             "No command provided",
	PARSEID_COMMAND_NOT_RECOGNISED: "Command `%s` not recognised",
	PARSEID_NO_INPUT:               "Command `%s` requires an argument",
	PARSEID_NOT_A_RIOT_ID:          "Input `%s` is not a riot id",
}

type ParseResult struct {
	command      int
	parseid      int
	errorMessage string
	arguments    interface{}
}

func Parse(message string) ParseResult {

	noInput := func(command int, commandString string) ParseResult {
		parseid := PARSEID_NO_INPUT
		return ParseResult{command: command, parseid: parseid, errorMessage: fmt.Sprintf(errorMessages[parseid], commandString)}
	}

	// The message has to start with the bot prefix
	if !strings.HasPrefix(message, prefix) {
		log.Debug().Msg("Reject message not intended for the bot")
		return ParseResult{parseid: PARSEID_NO_BOT_PREFIX}
	}

	// Get the command if valid
	words := strings.Split(strings.TrimSpace(message[len(prefix):]), " ")
	if len(words) == 1 && words[0] == "" {
		parseid := PARSEID_NO_COMMAND
		return ParseResult{parseid: parseid, errorMessage: errorMessages[parseid]}
	}
	commandString := words[0]
	words = words[1:]

	// Match the command

	switch commandString {
	case "register":
		// chanclol register <riot_id>
		command := COMMAND_REGISTER
		if len(words) == 0 {
			return noInput(command, commandString)
		} else {
			return parseRiotId(command, words)
		}
	case "unregister":
		// chanclol unregister <riot_id>
		command := COMMAND_UNREGISTER
		if len(words) == 0 {
			return noInput(command, commandString)
		} else {
			return parseRiotId(command, words)
		}
	case "rank":
		// chanclol rank <riot_id>
		command := COMMAND_RANK
		if len(words) == 0 {
			return noInput(command, commandString)
		} else {
			return parseRiotId(command, words)
		}
	case "channel":
		// chanclol channel <channel_name>
		command := COMMAND_CHANNEL
		if len(words) == 0 {
			return noInput(command, commandString)
		} else {
			return ParseResult{command: command, parseid: PARSEID_OK, arguments: strings.Join(words, " ")}
		}
	case "status":
		// chanclol status
		return ParseResult{command: COMMAND_STATUS, parseid: PARSEID_OK}
	case "help":
		// chanclol help
		return ParseResult{command: COMMAND_HELP, parseid: PARSEID_OK}
	default:
		parseid := PARSEID_COMMAND_NOT_RECOGNISED
		return ParseResult{parseid: parseid, errorMessage: fmt.Sprintf(errorMessages[parseid], commandString)}

	}

}

func parseRiotId(command int, words []string) ParseResult {

	// Check if the hashtag is present in the input
	word := strings.Join(words, "")
	hashtagPos := strings.Index(word, "#")
	if hashtagPos == -1 {
		parseid := PARSEID_NOT_A_RIOT_ID
		return ParseResult{command: command, parseid: parseid, errorMessage: fmt.Sprintf(errorMessages[parseid], word)}
	}

	// Prepare syntactically valid riot id
	parseid := PARSEID_OK
	gameName := word[:hashtagPos]
	tagLine := word[hashtagPos+1:]
	return ParseResult{parseid: parseid, command: command, arguments: riotapi.RiotId{GameName: gameName, TagLine: tagLine}}
}
