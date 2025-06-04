import argparse
import os
from dotenv import load_dotenv

import discord

from mt_bots.manager import Manager
from mt_bots.media_player import MediaPlayer


parser = argparse.ArgumentParser(description='Run a Discord bot')
parser.add_argument('--manager', action='store_true', help='Specifies manager bot')
parser.add_argument('--media_player', action='store_true', help='Specifies media player bot')
parser.add_argument('--token_var', required=True, help='Specifies the token variable name in .env file')

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

if not (parser.parse_args().manager or parser.parse_args().media_player):
    raise ValueError('You must specify either --manager or --media_player')
elif parser.parse_args().manager:
    bot = Manager(intents=intents, presence_msg='I broke the cutting board')
else:
    bot = MediaPlayer(intents=intents)

token_var = parser.parse_args().token_var
token = os.getenv(token_var)
if token is None:
    raise ValueError(f'No token found for {token_var} in .env file.')
bot.run(token)