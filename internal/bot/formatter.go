package bot

import (
	"fmt"

	"github.com/bwmarrin/discordgo"
)

type Response struct {
	content string
	embed   discordgo.MessageEmbed
}

func Welcome(channelName string) []Response {

	content := fmt.Sprintf("Hi, I will be sending messages to channel %s\n", channelName)
	content += "You can change this anytime by typing \n> `chanclol channel <channel_name>`"
	return []Response{{content: content}}
}

func InputNotValid(errorMessage string) []Response {

	return []Response{{content: fmt.Sprintf("Input not valid: \n> %s", errorMessage)}}
}

func HelpMessage() []Response {
	return []Response{}
}
