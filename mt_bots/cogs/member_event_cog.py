import discord
from discord.ext import commands


class MemberEventCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        system_channel = member.guild.system_channel
        if system_channel is not None:
            await system_channel.send(f'{member.mention} has entered the building 😏')
            
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        system_channel = member.guild.system_channel
        if system_channel is not None:
            await system_channel.send(f'{member.mention} has left the building 🤮')