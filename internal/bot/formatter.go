package bot

import (
	"chanclol/internal/riotapi"
	"fmt"
	"strings"

	"github.com/bwmarrin/discordgo"
)

// TODO: set the color of the embed messages

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

	embed := discordgo.MessageEmbed{Title: "Commands available"}
	embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{
		Name:   "`chanclol register <riot_id>`",
		Value:  "Register a player to automatically receive a message when the player has just started a new game",
		Inline: false,
	})
	embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{
		Name:   "`chanclol unregister <riot_id>`",
		Value:  "Unregister a player",
		Inline: false,
	})
	embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{
		Name:   "`chanclol rank <riot_id>`",
		Value:  "Print the current rank of the provided player",
		Inline: false,
	})
	embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{
		Name:   "`chanclol channel <new_channel_name>`",
		Value:  "Change the channel the bot sends messages to",
		Inline: false,
	})
	embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{
		Name:   "`chanclol status`",
		Value:  "Print the players currently registered, and the channel the bot is sending messages to",
		Inline: false,
	})
	embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{
		Name:   "`chanclol help`",
		Value:  "Print the usage of the different commands",
		Inline: false,
	})
	return []Response{{embed: embed}}
}

func NoResponseRiotApi(riotid riotapi.RiotId) []Response {
	return []Response{{content: fmt.Sprintf("Got no response from Riot API for player `%s`", &riotid)}}
}

func PlayerAlreadyRegistered(riotid riotapi.RiotId) []Response {
	return []Response{{content: fmt.Sprintf("Player `%s` is already registered", &riotid)}}
}

func PlayerRegistered(riotid riotapi.RiotId) Response {
	return Response{content: fmt.Sprintf("Player `%s` has been registered", &riotid)}
}

func PlayerUnregistered(riotid riotapi.RiotId) []Response {
	return []Response{{content: fmt.Sprintf("Player `%s` unregistered correctly", riotid)}}
}

func PlayerNotPreviouslyRegistered(riotid riotapi.RiotId) []Response {
	return []Response{{content: fmt.Sprintf("Player `%s` was not registered previously", riotid)}}
}

func PlayerRank(riotid riotapi.RiotId, leagues []riotapi.League) Response {

	if len(leagues) == 0 {
		return Response{content: fmt.Sprintf("Player `%s` is not ranked", &riotid)}
	} else {
		embed := discordgo.MessageEmbed{Title: fmt.Sprintf("Current rank of player `%s`", &riotid)}
		for _, league := range leagues {
			name := fmt.Sprintf("**%s**", league.QueueType)
			value := LeagueMessageValue(league)
			embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{Name: name, Value: value, Inline: false})
		}
		return Response{embed: embed}
	}
}

func LeagueMessageValue(league riotapi.League) string {

	return fmt.Sprintf("%s %s %d LPs. WR %f%% (%dW/%dL)", league.Tier, league.Rank, league.Lps, league.Winrate, league.Wins, league.Losses)
}

func ChannelDoesNotExist(channelName string) []Response {

	return []Response{{content: fmt.Sprintf("Channel `%s` does not exist in this server", channelName)}}
}

func ChannelChanged(channelName string) []Response {
	return []Response{{content: fmt.Sprintf("From now on, I will be sending ingame messages to `%s`", channelName)}}
}

func StatusMessage(riotids []riotapi.RiotId, channelName string) []Response {

	embed := discordgo.MessageEmbed{Title: "Configuration for this server"}

	// Players
	var field discordgo.MessageEmbedField
	if len(riotids) == 0 {
		field = discordgo.MessageEmbedField{
			Name:   "Players registered:",
			Value:  "None",
			Inline: false,
		}
	} else {
		stringSlice := func(riotids []riotapi.RiotId) []string {
			result := make([]string, len(riotids))
			for _, riotid := range riotids {
				result = append(result, fmt.Sprintf("%s", riotid))
			}
			return result
		}
		field = discordgo.MessageEmbedField{
			Name:   "Players registered:",
			Value:  strings.Join(stringSlice(riotids), ", "),
			Inline: false,
		}
	}
	embed.Fields = append(embed.Fields, &field)

	// Channel name
	embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{
		Name:   "Channel for in-game messages:",
		Value:  channelName,
		Inline: false,
	})

	return []Response{{embed: embed}}
}
