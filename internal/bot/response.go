package bot

import (
	"github.com/bwmarrin/discordgo"
	"github.com/rs/zerolog/log"
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
		log.Error().Err(err)
	}
}

func (response ResponseEmbed) Send(channelid string, discord *discordgo.Session) {
	if _, err := discord.ChannelMessageSendEmbed(channelid, &response.MessageEmbed); err != nil {
		log.Error().Err(err)
	}
}
