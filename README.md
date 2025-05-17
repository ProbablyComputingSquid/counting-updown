# Up vs Down Counting Bot

A Discord bot that implements a team-based counting game where two teams compete to reach their respective goals.

## Features

- Two teams: Counting Up (to 100) and Counting Down (to -100)
- Automatic team assignment based on team balance
- Team roles and statistics tracking
- Individual user statistics and leaderboard
- Penalties for breaking the sequence or counting twice in a row
- Moderation commands for managing the game

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory with your Discord bot token:
   ```
   DISCORD_TOKEN=your_bot_token_here
   ```
4. Run the bot:
   ```bash
   python main.py
   ```

## Commands

- `/start` - Start a counting game in the current channel (requires manage channels permission)
- `/stop` - Stop the counting game in the current channel (requires manage channels permission)
- `/count` - Check the current count in the game
- `/leaderboard` - View the server's counting leaderboard
- `/teamstats` - View team statistics
- `/switchteam` - Switch a player's team (requires manage roles permission)
- `/help` - Get help on available commands

## How to Play

1. A moderator starts the game in a channel using `/start`
2. Players are automatically assigned to teams when they first count
3. Team Up counts up (+1) to reach 100
4. Team Down counts down (-1) to reach -100
5. Players must alternate turns
6. Breaking the sequence or counting twice in a row gives the opposing team 5 counts
7. First team to reach their goal wins!

## Data Storage

The bot stores game statistics and active games in `db/counting_stats.json`. Make sure the `db` directory exists before running the bot. 