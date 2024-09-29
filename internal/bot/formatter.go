package bot

import (
	"chanclol/internal/riotapi"
	"fmt"
	"slices"
	"strings"
	"time"

	"github.com/bwmarrin/discordgo"
)

// Use "teal" color for the bot
const color int = 0x008080

func Welcome(channelName string) []Response {

	content := fmt.Sprintf("Hi, I will be sending messages to channel %s\n", channelName)
	content += "You can change this anytime by typing \n> `chanclol channel <channel_name>`"
	return []Response{ResponseString{content}}
}

func InputNotValid(errorMessage string) []Response {

	return []Response{ResponseString{fmt.Sprintf("Input not valid: \n> %s", errorMessage)}}
}

func HelpMessage() []Response {

	embed := discordgo.MessageEmbed{Title: "Commands available", Color: color}
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
	return []Response{ResponseEmbed{embed}}
}

func NoResponseRiotApi(riotid riotapi.RiotId) []Response {
	return []Response{ResponseString{fmt.Sprintf("Got no response from Riot API for player `%s`", &riotid)}}
}

func PlayerAlreadyRegistered(riotid riotapi.RiotId) []Response {
	return []Response{ResponseString{fmt.Sprintf("Player `%s` is already registered", &riotid)}}
}

func PlayerRegistered(riotid riotapi.RiotId) Response {
	return ResponseString{fmt.Sprintf("Player `%s` has been registered", &riotid)}
}

func PlayerUnregistered(riotid riotapi.RiotId) []Response {
	return []Response{ResponseString{fmt.Sprintf("Player `%s` unregistered correctly", riotid)}}
}

func PlayerNotPreviouslyRegistered(riotid riotapi.RiotId) []Response {
	return []Response{ResponseString{fmt.Sprintf("Player `%s` was not registered previously", riotid)}}
}

func PlayerRank(riotid riotapi.RiotId, leagues []riotapi.League) Response {

	if len(leagues) == 0 {
		return ResponseString{fmt.Sprintf("Player `%s` is not ranked", &riotid)}
	} else {
		embed := discordgo.MessageEmbed{Title: fmt.Sprintf("Current rank of player `%s`", &riotid), Color: color}
		for _, league := range leagues {
			name := fmt.Sprintf("**%s**", league.QueueType)
			value := LeagueMessageValue(league)
			embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{Name: name, Value: value, Inline: false})
		}
		return ResponseEmbed{embed}
	}
}

func LeagueMessageValue(league riotapi.League) string {

	return fmt.Sprintf("%s %s %d LPs. WR %d%% (%dW/%dL)", league.Tier, league.Rank, league.Lps, int(league.Winrate), league.Wins, league.Losses)
}

func ChannelDoesNotExist(channelName string) []Response {

	return []Response{ResponseString{fmt.Sprintf("Channel `%s` does not exist in this server", channelName)}}
}

func ChannelChanged(channelName string) []Response {
	return []Response{ResponseString{fmt.Sprintf("From now on, I will be sending ingame messages to `%s`", channelName)}}
}

func StatusMessage(riotids []riotapi.RiotId, channelName string) []Response {

	embed := discordgo.MessageEmbed{Title: "Configuration for this server", Color: color}

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
			for i := range riotids {
				result[i] = riotids[i].String()
			}
			return result
		}
		field = discordgo.MessageEmbedField{
			Name:   "Players registered:",
			Value:  strings.Join(stringSlice(riotids), "\n"),
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

	return []Response{ResponseEmbed{embed}}
}

func InGameMessage(puuid riotapi.Puuid, riotid riotapi.RiotId, spectator riotapi.Spectator) []Response {

	embed := discordgo.MessageEmbed{
		Title:       fmt.Sprintf("%s is in game (%s)", &riotid, spectator.GameMode),
		Description: fmt.Sprintf("Time elapsed: %d minutes", int64(spectator.GameLength.Minutes())),
		Color:       color,
	}
	// Get the team the player belongs to, so that it appears first
	var playerTeamId int
	var found bool = false
	for teamid, team := range spectator.Teams {
		for _, participant := range team {
			if participant.Puuid == puuid {
				playerTeamId = teamid
				found = true
				break
			}
		}
	}
	if !found {
		panic(fmt.Sprintf("Could not find player %s among the participants", &riotid))
	}
	// Create the list of teams, putting our player's team first
	teamids := make([]int, 0)
	for teamid := range spectator.Teams {
		if teamid == playerTeamId {
			teamids = slices.Insert(teamids, 0, teamid)
		} else {
			teamids = append(teamids, teamid)
		}
	}
	// Print the teams in the order just created
	for index, teamid := range teamids {
		AddInGameMessage(spectator.Teams[teamid], index, &embed)
	}
	return []Response{ResponseEmbed{embed}}
}

func AddInGameMessage(team riotapi.Team, index int, embed *discordgo.MessageEmbed) {

	name := fmt.Sprintf("**Team %d**", index+1)
	value := ""
	for _, participant := range team {
		value += fmt.Sprintf("**%s** (%s)\n", participant.ChampionName, participant.Riotid)
		if participant.Mastery.Available {
			lastPlayed := int64(time.Since(participant.Mastery.LastPlayed).Hours()) / 24
			value += fmt.Sprintf("- Mastery %d, %s\n", participant.Mastery.Level, FormatLastPlayed(lastPlayed))
		} else {
			value += "- Mastery not available\n"
		}
		for _, league := range participant.Leagues {
			value += fmt.Sprintf("- %s: %s\n", league.QueueType, LeagueMessageValue(league))
		}
	}
	embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{Name: name, Value: value})
}

func FormatLastPlayed(lastPlayed int64) string {
	if lastPlayed == 0 {
		return "last played today"
	} else if lastPlayed == 1 {
		return "last played yesterday"
	} else {
		return fmt.Sprintf("last played %d days ago", lastPlayed)
	}
}
