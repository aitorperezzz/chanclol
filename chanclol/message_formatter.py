import discord
import logging

from riot_id import RiotId
from riotapi.spectator import Spectator

logger = logging.getLogger(__name__)


color = discord.Color.teal()


class Message:
    def __init__(self, content: str | None, embed: discord.Embed | None):
        self.content = content
        self.embed = embed


def welcome(channel_name: str) -> Message:
    content = f"Hi, I will be sending messages to channel `{channel_name}`\n"
    content += "You can change this anytime by typing \n> `chanclol channel <new_channel_name>`"
    return Message(content, None)


def input_not_valid(error_string: str) -> Message:
    return Message(f"Input not valid: \n> {error_string}", None)


def player_already_registered(riot_id: RiotId) -> Message:
    return Message(f"Player `{riot_id}` is already registered", None)


def no_response_riot_api(riot_id: RiotId) -> Message:
    return Message(f"Got no response from Riot API for player `{riot_id}`", None)


def player_rank(riot_id: RiotId, league) -> Message:

    if not league or len(league) == 0:
        return Message(f"Player `{riot_id}` is not ranked", None)

    embed = discord.Embed(title=f"Current rank of player {riot_id}", color=color)
    for league in league:
        name = f"**{league.queue_type}**"
        # value = league_message_value(league)
        value = " "
        embed.add_field(name=name, value=value, inline=False)
    return Message(None, embed)


def player_registered(riot_id: RiotId) -> Message:
    return Message(f"Player `{riot_id}` has been registered", None)


def league_message_rank(league) -> str:
    return f"{league.tier[:3]} {league.rank} {league.lps} LPs"


def league_message_wr(league) -> str:
    return f"WR {league.win_rate}% ({league.wins}W/{league.losses}L)"


def player_unregistered_correctly(riot_id: RiotId) -> Message:
    return Message(f"Player `{riot_id}` unregistered correctly", None)


def player_not_previously_registered(riot_id: RiotId) -> Message:
    return Message(f"Player `{riot_id}` was not registered previously", None)


def print_config(riot_ids: list[RiotId], channel_name: str) -> Message:
    embed = discord.Embed(title=f"Configuration for this server", color=color)
    if len(riot_ids) == 0:
        embed.add_field(name="Players registered:", value="None", inline=False)
    else:
        embed.add_field(
            name="Players registered:", value=", ".join(str(riot_ids)), inline=False
        )
    embed.add_field(
        name="Channel for in-game messages:", value=channel_name, inline=False
    )
    return Message(None, embed)


def channel_does_not_exist(channel_name: str) -> Message:
    return Message(f"Channel `{channel_name}` does not exist in this server", None)


def channel_changed(channel_name: str) -> Message:
    return Message(
        f"From now on, I will be sending in-game messages in `{channel_name}`", None
    )


def create_help_message() -> Message:
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


def in_game_message(
    puuid: str, riot_id: RiotId, spectator: Spectator
) -> Message | None:

    embed = discord.Embed(
        title=f"{riot_id} is in game ({spectator.game_mode})",
        description=f"Time elapsed: {spectator.game_length_mins} minutes",
        color=color,
    )
    # Get the team the player belongs to. This will be the first team to appear in the message
    found_team_id = False
    for team_id in spectator.teams:
        for participant in spectator.teams[team_id]:
            if participant.puuid == puuid:
                player_team_id = team_id
                found_team_id = True
                break
        else:
            continue
        break
    if not found_team_id:
        logger.error(f"Player {riot_id} has not been found among the game participants")
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
