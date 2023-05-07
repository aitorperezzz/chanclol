import discord


color = discord.Color.teal()


class Message:
    def __init__(self, content, embed):
        self.content = content
        self.embed = embed


def welcome(channel_name):
    content = f'Hi, I will be sending messages to channel **{channel_name}**\n'
    content += 'You can change this anytime by typing `chanclol channel <new_channel_name>`'
    return Message(content, None)


def input_not_valid(error_string):
    return Message(f'Input not valid: \n> {error_string}', None)


def player_already_registered(player_name):
    return Message(f'Player **{player_name}** is already registered', None)


def no_response_league_api(player_name):
    return Message(f'Got no response from Riot API for player **{player_name}**', None)


def player_registered(player_name, league_info):
    content = f'Player **{player_name}** has been registered'
    if len(league_info) == 0:
        return Message(content, None)
    embed = discord.Embed(
        title=f'Current rank of player {player_name}',
        color=color
    )
    for league in league_info:
        name = f'**{league.queue_type}**'
        value = f'{league.tier} {league.rank} {league.lps} LPs\n'
        embed.add_field(name=name, value=value, inline=False)
    return Message(content, embed)


def player_unregistered_correctly(player_name):
    return Message(f'Player **{player_name}** unregistered correctly', None)


def player_not_previously_registered(player_name):
    return Message(f'Player **{player_name}** was not registered previously', None)


def print(players, channel_name):
    embed = discord.Embed(
        title=f'Configuration for this server',
        color=color
    )
    if len(players) == 0:
        embed.add_field(name='Players registered:', value='None', inline=False)
    else:
        embed.add_field(name='Players registered:',
                        value=', '.join(players.keys()), inline=False)
    embed.add_field(name='Channel for in-game messages:',
                    value=channel_name, inline=False)
    return Message(None, embed)


def channel_does_not_exist(channel_name):
    return Message(f'Channel **{channel_name}** does not exist in this server', None)


def channel_changed(channel_name):
    return Message(f'From now on, I will be sending in-game messages in **{channel_name}**', None)


def create_help_message():
    embed = discord.Embed(
        title=f'Commands available',
        color=color
    )
    embed.add_field(name='`chanclol register <player_name>`',
                    value='Register a new player', inline=False)
    embed.add_field(name='`chanclol unregister <player_name>`',
                    value='Unregister a player previously added', inline=False)
    embed.add_field(name='`chanclol print`',
                    value='Print the players currently registered, and the channel the bot is sending messages to', inline=False)
    embed.add_field(name='`chanclol channel <new_channel_name>`',
                    value='Change the channel the bot sends messages to', inline=False)
    embed.add_field(name='`chanclol help`',
                    value='Print the usage of the different commands', inline=False)
    return Message(None, embed)


def in_game_message(active_game_info, player_name):
    embed = discord.Embed(
        title=f'Player {player_name} is in game',
        description=f'Time elapsed: {active_game_info.game_length_minutes} minutes',
        color=color
    )
    # Get the team the player belongs to. This will be the first team to appear
    teams = [active_game_info.team_1, active_game_info.team_2]
    for index in range(len(teams)):
        add_in_game_team_message(teams[index], index, embed)
    return Message(None, embed)


def add_in_game_team_message(team, team_index, embed):
    name = f'**Team {team_index + 1}**'
    value = ''
    for participant in team:
        value += f'**{participant.champion_name}** ({participant.player_name})\n'
        if participant.mastery.available:
            value += f'- Mastery {participant.mastery.level}, played last time {participant.mastery.days_since_last_played} days ago\n'
        else:
            value += f'- Mastery not available\n'
        value += f'- {participant.spell1_name}, {participant.spell2_name}'
        value += '\n'
    embed.add_field(name=name, value=value)
