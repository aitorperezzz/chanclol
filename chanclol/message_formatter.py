import discord
import logging

logger = logging.getLogger(__name__)


color = discord.Color.teal()


class Message:
    def __init__(self, content, embed):
        self.content = content
        self.embed = embed


def welcome(channel_name):
    content = f"Hi, I will be sending messages to channel `{channel_name}`\n"
    content += "You can change this anytime by typing \n> `chanclol channel <new_channel_name>`"
    return Message(content, None)


def input_not_valid(error_string):
    return Message(f"Input not valid: \n> {error_string}", None)


def player_already_registered(player_name):
    return Message(f"Player `{player_name}` is already registered", None)


def no_response_riot_api(player_name):
    return Message(f"Got no response from Riot API for player `{player_name}`", None)


def player_rank(player_name, league):

    if not league or len(league) == 0:
        return Message(f"Player `{player_name}` is not ranked", None)

    embed = discord.Embed(title=f"Current rank of player {player_name}", color=color)
    for league in league:
        name = f"**{league.queue_type}**"
        # value = league_message_value(league)
        value = " "
        embed.add_field(name=name, value=value, inline=False)
    return Message(None, embed)


def player_registered(player_name):
    return Message(f"Player `{player_name}` has been registered", None)


def league_message_rank(league):
    return f"{league.tier[:3]} {league.rank} {league.lps} LPs"


def league_message_wr(league):
    return f"WR {league.win_rate}% ({league.wins}W/{league.losses}L)"


def player_unregistered_correctly(player_name):
    return Message(f"Player `{player_name}` unregistered correctly", None)


def player_not_previously_registered(player_name):
    return Message(f"Player `{player_name}` was not registered previously", None)


def print_config(player_names, channel_name):
    embed = discord.Embed(title=f"Configuration for this server", color=color)
    if len(player_names) == 0:
        embed.add_field(name="Players registered:", value="None", inline=False)
    else:
        embed.add_field(
            name="Players registered:", value=", ".join(player_names), inline=False
        )
    embed.add_field(
        name="Channel for in-game messages:", value=channel_name, inline=False
    )
    return Message(None, embed)


def channel_does_not_exist(channel_name):
    return Message(f"Channel `{channel_name}` does not exist in this server", None)


def channel_changed(channel_name):
    return Message(
        f"From now on, I will be sending in-game messages in `{channel_name}`", None
    )


def create_help_message():
    embed = discord.Embed(title=f"Commands available", color=color)
    embed.add_field(
        name="`chanclol register <riot_id>`",
        value="Register a player to automatically receive a message when the player has just started a new game",
        inline=False,
    )
    embed.add_field(
        name="`chanclol unregister <riot_id>`",
        value="Unregister a player",
        inline=False,
    )
    embed.add_field(
        name="`chanclol rank <riot_id>`",
        value="Print the current rank of the provided player",
        inline=False,
    )
    embed.add_field(
        name="`chanclol print`",
        value="Print the players currently registered, and the channel the bot is sending messages to",
        inline=False,
    )
    embed.add_field(
        name="`chanclol channel <new_channel_name>`",
        value="Change the channel the bot sends messages to",
        inline=False,
    )
    embed.add_field(
        name="`chanclol help`",
        value="Print the usage of the different commands",
        inline=False,
    )
    return Message(None, embed)


def in_game_message(puuid, player_name, spectator):
    embed = discord.Embed(
        title=f"{player_name} is in game ({spectator.game_mode})",
        description=f"Time elapsed: {spectator.game_length_minutes} minutes",
        color=color,
    )
    # Get the team the player belongs to. This will be the first team to appear in the message
    player_team_id = None
    for team_id in spectator.teams:
        for participant in spectator.teams[team_id]:
            if participant.puuid == puuid:
                player_team_id = team_id
                break
        else:
            continue
        break
    if player_team_id == None:
        logger.error(
            f"Player {player_name} has not been found among the game participants"
        )
        return None
    # Create a list of team ids where the player's one is the first
    team_ids = list(spectator.teams)
    team_ids.insert(0, team_ids.pop(team_ids.index(player_team_id)))
    # Print the teams in the order just created
    for index in range(len(team_ids)):
        add_in_game_team_message(spectator.teams[team_ids[index]], index, embed)
    return Message(None, embed)


def add_in_game_team_message(team, team_index, embed):
    name = f"**Team {team_index + 1}**"
    value = ""
    for participant in team:
        # Get the data to display
        mastery = f"{participant.mastery.level}" if participant.mastery else "-"
        days_wo_play = (
            f"{participant.mastery.days_since_last_played} days ago"
            if participant.mastery
            else "Never"
        )
        league_solo = ["-", "-"]
        league_flex = ["-", "-"]
        if participant.league:
            for league in participant.league:
                if league.queue_type == "R. Solo":
                    league_solo = [
                        league_message_rank(league),
                        league_message_wr(league),
                    ]
                elif league.queue_type == "R. Flex":
                    league_flex = [
                        league_message_rank(league),
                        league_message_wr(league),
                    ]
        # Display
        value += f"- {participant.champion_name} {participant.riot_id_string}\n"
        value += "```"
        table = {
            "Mastery": mastery,
            "Played": days_wo_play,
            "Solo": league_solo,
            "Flex": league_flex,
        }
        title_len = len(max(table.keys(), key=len))
        for title in table:
            new_title = title.ljust(title_len, " ")
            match title:
                case "Solo":
                    value += f"{new_title}  {table[title][0]}\n"
                    value += f" {" " * title_len}  {table[title][1]}"
                case "Flex":
                    value += f"{new_title}  {table[title][0]}\n"
                    value += f" {" " * title_len}  {table[title][1]}"
                case _:
                    value += f"{new_title}  {table[title]}\n"
        value += "```\n"
        # if participant.mastery:
        #     value += f"- Mastery {participant.mastery.level}, last played {participant.mastery.days_since_last_played} days ago\n"
        # else:
        #     value += f"- Mastery not available\n"
        # if participant.league:
        #     for league in participant.league:
        #         value += f"- {league.queue_type}: {league_message_value(league)}\n"
    embed.add_field(name=name, value=value)
