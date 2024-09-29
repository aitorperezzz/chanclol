package bot

import (
	"fmt"

	"github.com/bwmarrin/discordgo"
)

type ResponseString struct {
	string
}
type ResponseEmbed struct {
	discordgo.MessageEmbed
}

type Response interface {
	Send(channelid string, discordgo *discordgo.Session)
}

func (response ResponseString) Send(channelid string, discord *discordgo.Session) {
	if _, err := discord.ChannelMessageSend(channelid, response.string); err != nil {
		fmt.Println(err)
	}
}

func (response ResponseEmbed) Send(channelid string, discord *discordgo.Session) {
	if _, err := discord.ChannelMessageSendEmbed(channelid, &response.MessageEmbed); err != nil {
		fmt.Println(err)
	}
}
