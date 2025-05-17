import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
import json
from typing import Dict, Optional, Tuple
from pathlib import Path
import random
import numexpr as ne

load_dotenv()

# Create a bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# File to store statistics
STATS_FILE = 'db/counting_stats.json'

# Team roles
UP_TEAM_ROLE = "Counting Up"
DOWN_TEAM_ROLE = "Counting Down"

def ensure_db_dir():
    """Ensure the db directory exists"""
    Path('db').mkdir(exist_ok=True)

def load_stats() -> Dict[str, Dict[str, Dict[str, int]]]:
    """Load statistics from JSON file"""
    ensure_db_dir()
    if not Path(STATS_FILE).exists():
        return {}
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_stats(stats: Dict[str, Dict[str, Dict[str, int]]]):
    """Save statistics to JSON file"""
    ensure_db_dir()
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        print(f"Error saving stats: {e}")

def load_games() -> Dict[int, dict]:
    """Load active games from JSON file"""
    ensure_db_dir()
    if not Path(STATS_FILE).exists():
        return {}
    try:
        with open(STATS_FILE, 'r') as f:
            data = json.load(f)
            return data.get('active_games', {})
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_games(games: Dict[int, dict]):
    """Save active games to JSON file"""
    ensure_db_dir()
    try:
        data = load_stats()
        data['active_games'] = games
        with open(STATS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving games: {e}")

# Load existing stats and games
global stats
global active_games
stats = load_stats()
active_games = load_games()

def get_user_stats(guild_id: str, user_id: str) -> Dict[str, int]:
    """Get or initialize user stats"""
    if guild_id not in stats:
        stats[guild_id] = {}
    if 'users' not in stats[guild_id]:
        stats[guild_id]['users'] = {}
    if user_id not in stats[guild_id]['users']:
        stats[guild_id]['users'][user_id] = {
            'counts': 0,
            'wins': 0,
            'fails': 0
        }
    return stats[guild_id]['users'][user_id]

async def get_or_create_roles(guild: discord.Guild) -> Tuple[discord.Role, discord.Role]:
    """Get or create the team roles"""
    up_role = discord.utils.get(guild.roles, name=UP_TEAM_ROLE)
    down_role = discord.utils.get(guild.roles, name=DOWN_TEAM_ROLE)
    
    if not up_role:
        up_role = await guild.create_role(name=UP_TEAM_ROLE, color=discord.Color.blue())
    if not down_role:
        down_role = await guild.create_role(name=DOWN_TEAM_ROLE, color=discord.Color.red())
    
    return up_role, down_role

async def assign_team(member: discord.Member, up_role: discord.Role, down_role: discord.Role) -> discord.Role:
    """Assign member to the team with fewer members"""
    up_count = len(up_role.members)
    down_count = len(down_role.members)
    
    if up_count <= down_count:
        await member.add_roles(up_role)
        return up_role
    else:
        await member.add_roles(down_role)
        return down_role

@bot.event
async def on_ready():
    print(f'We\'re in!{bot.user} has connected to Discord')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    # Reload stats and games on startup
    global stats, active_games
    stats = load_stats()
    active_games = load_games()
    print(f"Loaded stats and active games from disk. Active games: {active_games}")
    
    # Process any messages that were sent while the bot was offline
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.id in active_games:
                print(f"Found active counting game in channel {channel.name} ({channel.id})")
                try:
                    async for message in channel.history(limit=1):
                        if message.author != bot.user:
                            await bot.process_commands(message)
                except Exception as e:
                    print(f"Error processing messages in channel {channel.name}: {e}")

@bot.tree.command(name="ping", description="Check the bot's latency")
async def ping(interaction: discord.Interaction):
    """Check the bot's latency"""
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f'Pong! 🏓 Latency: {latency}ms')

@bot.tree.command(name="help", description="Get some help on commands")
async def help(interaction: discord.Interaction):
    """Get some help on commands"""
    await interaction.response.send_message(
        f'''
        Here are the available commands:
         \- /start marks a channel as counting mod only)
         \- /count checks the current count in the game
         \- /leaderboard shows the server's counting leaderboard (it has two paramaters, team and page)
         \- /teamstats shows the team statistics
         \- /switchteam switches a player's team (mod only)
         \- /ping checks latency 
         \- /help shows this message
         \- /stop stops the counting in this channel (mod only)
         ''',
         ephemeral=True
    )

@bot.tree.command(name="start", description="Start a counting in this channel (mod only)")
@app_commands.checks.has_permissions(manage_channels=True)
async def start_game(interaction: discord.Interaction):
    """Start a team counting game in the current channel"""
    channel_id = interaction.channel_id
    
    if channel_id in active_games:
        await interaction.response.send_message("counting is already active in this channel!", ephemeral=True)
        return
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("You don't have permission to set this channel as a counting channel!", ephemeral=True)
        return
    # Get or create team roles
    up_role, down_role = await get_or_create_roles(interaction.guild)
    
    active_games[channel_id] = {
        "current_number": 0,
        "last_counter": None,
        "channel_id": channel_id,
        "guild_id": str(interaction.guild_id),
        "up_role_id": up_role.id,
        "down_role_id": down_role.id
    }
    
    # Save the new game to the database
    save_games(active_games)
    
    await interaction.response.send_message(
        f"the counting has started! \n"
        f"Team {UP_TEAM_ROLE} is counting up to 100\n"
        f"Team {DOWN_TEAM_ROLE} is counting down to -100\n"
        f"Start counting from 0!\n\n"
        f"Players will be automatically assigned to teams when they first count"
    )

@bot.tree.command(name="stop", description="Stop the counting game in this channel (mod only)")
@app_commands.checks.has_permissions(manage_channels=True)
async def stop_game(interaction: discord.Interaction):
    """Stop the counting game in the current channel"""
    channel_id = interaction.channel_id
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("You don't have permission to stop the counting in this channel!", ephemeral=True)
        return
    if channel_id not in active_games:
        await interaction.response.send_message("No counting game is active in this channel!", ephemeral=True)
        return
    
    del active_games[channel_id]
    # Save the updated games to the database
    save_games(active_games)
    await interaction.response.send_message("Counting game stopped!")

@bot.tree.command(name="teamstats", description="View team statistics")
async def team_stats(interaction: discord.Interaction):
    """View statistics for both teams"""
    guild_id = str(interaction.guild_id)
    
    # Get team stats
    guild_stats = stats.get(guild_id, {})
    up_wins = guild_stats.get('up_wins', 0)
    down_wins = guild_stats.get('down_wins', 0)
    
    # Get current team sizes
    up_role = discord.utils.get(interaction.guild.roles, name=UP_TEAM_ROLE)
    down_role = discord.utils.get(interaction.guild.roles, name=DOWN_TEAM_ROLE)
    
    up_count = len(up_role.members) if up_role else 0
    down_count = len(down_role.members) if down_role else 0
    
    embed = discord.Embed(title="Team Statistics", color=discord.Color.blue())
    embed.add_field(name=f"{UP_TEAM_ROLE} Wins", value=str(up_wins))
    embed.add_field(name=f"{DOWN_TEAM_ROLE} Wins", value=str(down_wins))
    embed.add_field(name=f"{UP_TEAM_ROLE} Members", value=str(up_count))
    embed.add_field(name=f"{DOWN_TEAM_ROLE} Members", value=str(down_count))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="switchteam", description="Switch a player's team (Moderator only)")
@app_commands.checks.has_permissions(manage_roles=True)
async def switch_team(interaction: discord.Interaction, user: discord.Member):
    """Switch a player's team (Moderator only)"""
    up_role, down_role = await get_or_create_roles(interaction.guild)
    
    if up_role in user.roles:
        await user.remove_roles(up_role)
        await user.add_roles(down_role)
        await interaction.response.send_message(f"{user.mention} has been switched to team {DOWN_TEAM_ROLE}!")
    elif down_role in user.roles:
        await user.remove_roles(down_role)
        await user.add_roles(up_role)
        await interaction.response.send_message(f"{user.mention} has been switched to team {UP_TEAM_ROLE}!")
    else:
        # If user is not in any team, assign them to the team with fewer members
        assigned_role = await assign_team(user, up_role, down_role)
        await interaction.response.send_message(f"{user.mention} has been assigned to team {assigned_role.name}!")

@bot.tree.command(name="count", description="Check the current count in the channel")
async def check_count(interaction: discord.Interaction):
    """Check the current count in the game"""
    global active_games
    active_games = load_games()  # Reload games to ensure we have latest state
    
    channel_id = str(interaction.channel_id)
    
    if channel_id not in active_games:
        await interaction.response.send_message("No counting game is active in this channel!", ephemeral=True)
        return
    
    game = active_games[channel_id]
    current_number = game["current_number"]
    
    embed = discord.Embed(title="Current Count", color=discord.Color.blue())
    embed.add_field(name="Count", value=str(current_number))
    
    # Add progress information
    if current_number > 0:
        progress = f"Team Up: {current_number}/100"
    elif current_number < 0:
        progress = f"Team Down: {abs(current_number)}/100"
    else:
        progress = "Game just started!"
    
    embed.add_field(name="Progress", value=progress)
    await interaction.response.send_message(embed=embed)

# i think this command no longer needs to exist
@bot.tree.command(name="printrawstats", description="Print the raw stats")
async def print_raw_stats(interaction: discord.Interaction):
    """Print the raw stats"""
    await interaction.response.send_message(str(stats))

@bot.tree.command(name="leaderboard", description="View the server's counting leaderboard")
@app_commands.choices(team=[
    app_commands.Choice(name="Up", value="up"),
    app_commands.Choice(name="Down", value="down")
])
async def leaderboard(interaction: discord.Interaction, team: Optional[app_commands.Choice[str]] = None, page: int = 1):
    """View the server's counting leaderboard"""
    global stats
    #print(stats)
    guild_id = str(interaction.guild_id)
    
    if guild_id not in stats or 'users' not in stats[guild_id]:
        await interaction.response.send_message("No counting statistics available yet - go count, you fools!", ephemeral=True)
        return
    
    # Get user stats and sort by counts
    user_stats = stats[guild_id]['users']
    sorted_users = sorted(
        user_stats.items(),
        key=lambda x: (x[1]['counts'], x[1]['wins']),
        reverse=True
    )
    
    if team:
        team_value = 1 if team.value == 'up' else -1
        sorted_users = [user for user in sorted_users if getTeam(int(user[0]), interaction.guild) == team_value]
    
    total_pages = (len(sorted_users) + 9) // 10
    if page < 1 or page > total_pages:
        await interaction.response.send_message("Invalid page number!", ephemeral=True)
        return

    # Create embed
    embed = discord.Embed(
        title=f'Top counters in {interaction.guild.name}',
        description=f'Page {page} of {total_pages}',
        color=discord.Color.gold()
    )
    
    # Add top 10 users to embed
    for i, (user_id, user_data) in enumerate(sorted_users[(page-1) * 10: page * 10], 1):
        user = interaction.guild.get_member(int(user_id))
        if user:
            team_value = getTeam(int(user_id), interaction.guild)
            team_emoji = "⬆️" if team_value == 1 else "⬇️" if team_value == -1 else "❓"
            embed.add_field(
                name=f"{i}. {user.display_name} {team_emoji}",
                value=f"Counts: {user_data['counts']} | Wins: {user_data['wins']} | Fails: {user_data.get('fails', 0)}",
                inline=False
            )
    
    await interaction.response.send_message(embed=embed)

# handle messages from users
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    channel_id = str(message.channel.id)
    if channel_id not in active_games:
        return
    
    # Ensure we have the latest game state
    game = active_games.get(channel_id)
    if not game:
        print(f"Warning: Channel {channel_id} marked as active but no game data found")
        return
    
    # Check if the message is a number
    m = message.content.strip()
    if m.lower() == "your mother":
        await message.add_reaction("✅")
        return
    m = m.split(" ")
    try:
        number = int(ne.evaluate(''.join(m)))
    except Exception as e:
        try:
            number = int(ne.evaluate(m[0]))
        except: 
            pass
        return
    
    # Get user's team
    up_role = message.guild.get_role(game["up_role_id"])
    down_role = message.guild.get_role(game["down_role_id"])
    
    # If user is not in a team, assign them to the team with fewer members
    if not (up_role in message.author.roles or down_role in message.author.roles):
        assigned_role = await assign_team(message.author, up_role, down_role)
        await message.channel.send(f"Welcome {message.author.mention}! You've been assigned to team {assigned_role.name}! Your next count will be registered.")
        return
    
    # Determine if user is counting up or down
    is_counting_up = up_role in message.author.roles
    
    # Check if it's the next number in sequence
    expected_number = game["current_number"] + 1 if is_counting_up else game["current_number"] - 1
    if number != expected_number:
        if game["last_counter"] == None: # warn the user because count reset
            await message.add_reaction('⚠️')
            await message.channel.send(f"{message.author.mention} someone just ruined the count! make sure to count the right number next time!. counting starts from  {game['current_number']}")
            return
        
        # Update user's fail count
        guild_id = str(message.guild.id)
        user_stats = get_user_stats(guild_id, str(message.author.id))
        user_stats['fails'] += 1
        save_stats(stats)
        
        await message.add_reaction('❌')
        if is_counting_up:
            game["current_number"] -= 5
        else:
            game["current_number"] += 5
        await message.channel.send(f"❌ {message.author.mention} broke the sequence! The opposing team gets 5 counts. The count is now {game['current_number']}.")
        game["last_counter"] = None
        save_games(active_games)
        return
    
    # Check if the same person is counting twice in a row
    if message.author.id == game["last_counter"]:
        if game["last_counter"] == None: # warn the user because count reset
            await message.add_reaction('⚠️')
            await message.channel.send(f"{message.author.mention} someone just ruined the count! make sure to count the right number next time!. counting starts from  {game['current_number']}")
            return
        
        # Update user's fail count
        guild_id = str(message.guild.id)
        user_stats = get_user_stats(guild_id, str(message.author.id))
        user_stats['fails'] += 1
        save_stats(stats)
        
        await message.add_reaction('❌')
        if is_counting_up:
            game["current_number"] -= 5
        else:
            game["current_number"] += 5
        await message.channel.send(f"❌ {message.author.mention} can't count twice in a row! The opposing team gets 5 counts. The count is now {game['current_number']}.")
        game["last_counter"] = None
        save_games(active_games)
        return
    
    # Valid count
    game["current_number"] = number
    game["last_counter"] = message.author.id
    
    # Update user stats
    guild_id = str(message.guild.id)
    user_stats = get_user_stats(guild_id, str(message.author.id))
    user_stats['counts'] += 1
    
    # Check for win condition
    if number >= 100 or number <= -100:
        winning_team = UP_TEAM_ROLE if number >= 100 else DOWN_TEAM_ROLE
        guild_id = str(message.guild.id)
        
        # Update team stats
        if guild_id not in stats:
            stats[guild_id] = {}
        if 'up_wins' not in stats[guild_id]:
            stats[guild_id]['up_wins'] = 0
        if 'down_wins' not in stats[guild_id]:
            stats[guild_id]['down_wins'] = 0
        
        if winning_team == UP_TEAM_ROLE:
            stats[guild_id]['up_wins'] += 1
        else:
            stats[guild_id]['down_wins'] += 1
        
        # Update user win count
        user_stats['wins'] += 1
        
        # Save both stats and games
        save_stats(stats)
        save_games(active_games)
        await message.add_reaction('🎉')
        await message.channel.send(f"🎉 Team {winning_team} has won! The count has been reset to 0.")
        game["current_number"] = 0
        game["last_counter"] = None
        return
    
    # Add reaction to confirm valid count
    await message.add_reaction('✅')
    # Save both stats and games
    save_stats(stats)
    save_games(active_games)

def getTeam(user_id: int, guild: discord.Guild) -> int:
    """Get user's team based on roles. Returns -1 for down, 1 for up, 0 for none"""
    member = guild.get_member(user_id)
    if not member:
        return 0
    
    up_role = discord.utils.get(guild.roles, name=UP_TEAM_ROLE)
    down_role = discord.utils.get(guild.roles, name=DOWN_TEAM_ROLE)
    
    if up_role in member.roles:
        return 1
    elif down_role in member.roles:
        return -1
    return 0

TOKEN = os.getenv('DISCORD_TOKEN')

if __name__ == '__main__':
    bot.run(TOKEN)
