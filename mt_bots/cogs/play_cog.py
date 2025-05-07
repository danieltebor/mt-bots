import logging
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands, ui

from yt_dlp import YoutubeDL


YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'logger': None
}
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -analyzeduration 0 -loglevel 0',
    'options': '-vn'
}

class PlayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.vc = None
        self.player_message = None
        self.player_controls_view = MediaControlView(self)
        self.current_media = None
        self.queue = []
        self.is_playing = False
        self.is_paused = False
        
    async def _reset(self):
        if self.vc and self.vc.is_connected():
            self.vc.stop()
            await self.vc.disconnect()
        self.vc = None
        
        if self.player_message:
            try:
                await self.player_message.delete()
            except discord.NotFound:
                pass
        self.player_message = None
        
        self.current_media = None
        self.queue = []
        self.is_playing = False
        self.is_paused = False
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member != self.bot.user:
            return
        
        if before.channel is not None \
            and after.channel is None \
            and (self.is_playing or self.is_paused):
                await self._reset()
                
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if self.player_message and payload.message_id == self.player_message.id:
            await self._reset()
    
    @app_commands.command(name='play', description='Play media in a voice channel.')
    @app_commands.describe(query='The name of the media or the URL of the media you want to play')
    async def play(self, interaction: discord.Interaction, query: str):
        if not self._user_connected_to_vc(interaction):
            await interaction.response.send_message(
                'You are not connected to a voice channel',
                ephemeral=True, delete_after=5
            )
            return
        
        permissions = interaction.user.voice.channel.permissions_for(interaction.guild.me)
        if not permissions.view_channel:
            await interaction.response.send_message(
                'I do not have permission to view your voice channel',
                ephemeral=True, delete_after=5
            )
            return
        elif not permissions.connect:
            await interaction.response.send_message(
                'I do not have permission to connect to your voice channel',
                ephemeral=True, delete_after=5
            )
            return
        elif not permissions.speak:
            await interaction.response.send_message(
                'I do not have permission to speak in your voice channel',
                ephemeral=True, delete_after=5
            )
            return
        
        if self.is_playing or self.is_paused:
            media_info = self._search_yt(query)
            if not media_info:
                await interaction.response.send_message(
                    'No media found for that query',
                    ephemeral=True, delete_after=5
                )
                return
            media_info = self._extract_fields_from_media_info(media_info)
            self.queue.append(media_info)
            await self._update_player_embed()
            title = media_info['title']
            await interaction.response.send_message(
                f'Added {title} to the queue',
                ephemeral=True, delete_after=5
            )
            return
        
        await interaction.response.defer(thinking=True)
        
        media_info = self._search_yt(query)
        if not media_info:
            await interaction.followup.send(
                'No media found for that query',
                ephemeral=True, delete_after=5
            )
            return
        media_info = self._extract_fields_from_media_info(media_info)
        
        self.vc = await interaction.user.voice.channel.connect()
        self.current_media = media_info # Set for initial embed.
        self.is_playing = True
        embed = self._create_player_embed()
        self.player_message = await interaction.followup.send(
            embed=embed,
            view=self.player_controls_view,
        )
        
        self.queue.append(media_info)
        self._play_next()
            
    def _search_yt(self, query: str) -> Optional[dict]:
        with YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(f'ytsearch:{query}', download=False)
                if 'entries' in info and len(info['entries']) > 0:
                    return info['entries'][0]
                return None
            except Exception as e:
                logger = logging.getLogger('discord')
                logger.error(f'Error searching for {query}: {e}')
        return None
    
    def _extract_fields_from_media_info(self, media_info: dict) -> dict:
        fields = {
            'title': media_info.get('title'),
            'url': self._get_best_audio_url(media_info),
            'thumbnail': media_info.get('thumbnail'),
            'duration': media_info.get('duration'),
            'uploader': media_info.get('uploader'),
            'description': media_info.get('description')
        }
        return fields
    
    def _get_best_audio_url(self, media_info: dict) -> Optional[str]:
        if 'formats' not in media_info or not media_info['formats']:
            return media_info.get('url')
        
        formats = media_info['formats']
        
        # Check for opus since Discord uses it internally.
        for format in formats:
            if format.get('acodec') == 'opus' and format.get('vcodec') in ('none', 'null'):
                return format['url']
            
        # Audio only formats.
        for format in formats:
            if format.get('vcodec') in ('none', 'null') and format.get('acodec') != 'none':
                return format['url']
            
        # Fallback to any format with audio.
        for format in formats:
            if format.get('acodec') != 'none' and format.get('url'):
                return format['url']
        
        return media_info.get('url')
    
    def _play_next(self):
        if len(self.queue) > 0:
            self.current_media = self.queue.pop(0)
            url = self.current_media['url']
            
            self.vc.play(
                discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS),
                after=lambda _: self._play_next()
            )
            
            self.bot.loop.create_task(self._update_player_embed())
        else:
            self.bot.loop.create_task(self._reset())
    
    def _create_player_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title='🎵 Media Player',
            color=discord.Color.blurple()
        )
        
        if self.current_media:
            embed.add_field(
                name='🔊 Now Playing',
                value=self.current_media['title'],
                inline=False
            )
            embed.set_thumbnail(url=self.current_media['thumbnail'])
        else:
            embed.add_field(
                name='🔊 Now Playing',
                value='-',
                inline=False
            )
            
        if len(self.queue) > 0:
            queue_text = ''
            for i, media in enumerate(self.queue[:5]):
                title = media['title']
                queue_text += f'**{i + 1}.** {title}\n'
                
            if len(self.queue) > 5:
                queue_text += f'...and {len(self.queue) - 5} more'
                
            embed.add_field(
                name=f'📜 Queue {len(self.queue)}',
                value=queue_text,
                inline=False
            )
        else:
            embed.add_field(
                name='📜 Queue (0)',
                value='-',
                inline=False
            )
            
        status = 'Status:'
        status = status + '▶️ Playing' if self.is_playing else '⏸️ Paused'
        embed.set_footer(text=status)
        
        return embed
    
    async def _update_player_embed(self):
        if not self.player_message:
            return
        
        try:
            embed = self._create_player_embed()
            await self.player_message.edit(embed=embed)
        except discord.NotFound:
            self._reset()
    
    def _user_connected_to_vc(self, interaction: discord.Interaction) -> bool:
        if interaction.user.voice:
            return True
        return False
    
    def _user_in_same_vc(self, interaction: discord.Interaction) -> bool:
        if not self._user_connected_to_vc(interaction):
            return False
        
        if self.vc is None:
            return False
        
        return interaction.user.voice.channel.id == self.vc.channel.id

class MediaControlView(ui.View):
    def __init__(self, cog: PlayCog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @ui.button(label='⏯️', style=discord.ButtonStyle.primary)
    async def pause_resume(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_user_vc(interaction):
            return
        
        if self.cog.is_paused:
            self.cog.is_playing = True
            self.cog.is_paused = False
            self.cog.vc.resume()
            await interaction.response.send_message(
                '▶️ Resumed playback',
                ephemeral=True, delete_after=5
            )
        else:
            self.cog.is_playing = False
            self.cog.is_paused = True
            self.cog.vc.pause()
            await interaction.response.send_message(
                '⏸️ Paused playback',
                ephemeral=True, delete_after=5
            )
            
        await self.cog._update_player_embed()
    
    @ui.button(label='⏭️', style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_user_vc(interaction):
            return
        
        if len(self.cog.queue) > 0:
            self.cog.is_playing = True
            self.cog.is_paused = False
            self.cog.vc.stop()
            await self.cog._update_player_embed()
            await interaction.response.send_message(
                '⏭️ Skipped to the next media',
                ephemeral=True, delete_after=5
            )
        else:
            await interaction.response.send_message(
                'No more media in the queue, stopping playback',
                ephemeral=True, delete_after=5
            )
            await self.cog._reset()
            return
    
    @ui.button(label='⏹️', style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_user_vc(interaction):
            return
        
        await interaction.response.send_message(
            '⏹️ Stopping playback and disconnecting from the voice channel',
            ephemeral=True, delete_after=5
        )
        await self.cog._reset()

    async def _check_user_vc(self, interaction: discord.Interaction):
        if not self.cog._user_connected_to_vc(interaction):
            await interaction.response.send_message(
                'You must be connected to a voice channel to use this button',
                ephemeral=True, delete_after=5
            )
            return False
        elif not self.cog._user_in_same_vc(interaction):
            await interaction.response.send_message(
                'You must be in the same voice channel as me to use this button',
                ephemeral=True, delete_after=5
            )
            return False
        return True