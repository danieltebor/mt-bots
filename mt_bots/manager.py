import logging

import discord
from discord.ext import commands

from mt_bots.cogs.member_event_cog import MemberEventCog


class Manager(commands.Bot):
    def __init__(self, intents: discord.Intents, presence_msg: str = None):
        super().__init__(command_prefix='\u200b', intents=intents)
        self.logger = logging.getLogger('discord')
        self.presence_msg = presence_msg
        
    async def setup_hook(self):
        await self.add_cog(MemberEventCog(self))
        
    async def on_ready(self):
        self.logger.info(f'Manager object logged in as {self.user.name} (ID: {self.user.id})')
        
        await self.tree.sync()
        if self.presence_msg:
            await self.change_presence(activity=discord.CustomActivity(
                name=self.presence_msg
            ))