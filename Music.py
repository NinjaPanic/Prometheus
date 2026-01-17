import discord
import yt_dlp
import asyncio
import time
from discord import app_commands, ui, Interaction
from collections import deque

# This file contains the music system extracted from Prometheus.py
# It is kept here as a backup/archive.

# ========== VARIABLES ==========
SONG_QUEUES = {}
BROWSER = "brave" # or your browser

# ========== CLASS & FUNCTION ==========

class MusicControlView(discord.ui.View):
    def __init__(self, voice_client, guild_id, channel):
        super().__init__(timeout=None)
        self.voice_client = voice_client
        self.guild_id = guild_id
        self.channel = channel

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        user_voice = interaction.user.voice
        bot_voice = self.voice_client.channel

        if user_voice is None or user_voice.channel != bot_voice:
            await interaction.response.send_message("You must be in the same voice chat room as the bot to use these buttons.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.primary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            await interaction.response.send_message("Playback paused.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @discord.ui.button(label="Resume", style=discord.ButtonStyle.success)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_paused():
            self.voice_client.resume()
            await interaction.response.send_message("Playback resumed.", ephemeral=True)
        else:
            await interaction.response.send_message("Playback is not paused.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            await interaction.response.send_message("Skipped current song.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing to skip.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Stopped playback and disconnecting...", ephemeral=True)

        async def stop_and_cleanup():
            if self.voice_client.is_connected():
                self.voice_client.stop()
                await self.voice_client.disconnect()
                SONG_QUEUES[self.guild_id].clear()

        asyncio.create_task(stop_and_cleanup())

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)

def truncate(text, max_length=1024):
    return text if len(text) <= max_length else text[:max_length-3] + "..."

async def play_next_song(voice_client, guild_id, channel):
    if SONG_QUEUES[guild_id]:
        audio_url, title, author, duration, thumbnail = SONG_QUEUES[guild_id].popleft()

        embed = discord.Embed(title=truncate(title), description=f"Par {truncate(author)}", color=0x1DB954)
        embed.add_field(name="Durée", value=duration or "Inconnue", inline=True)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -c:a libopus -b:a 96k",
        }

        source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable="ffmpeg\\ffmpeg.exe")

        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), client.loop)

        voice_client.play(source, after=after_play)

        view = MusicControlView(voice_client, guild_id, channel)
        await channel.send(embed=embed, view=view)
    else:
        await voice_client.disconnect()
        SONG_QUEUES[guild_id] = deque()

# ========== COMMANDS / ==========

# Note: These commands need to be re-integrated into a Bot/Client instance to work.

# --- Skip ---
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped the current song.")
    else:
        await interaction.response.send_message("Not playing anything to skip.")

# --- Pause ---
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client is None:
        return await interaction.response.send_message("I'm not in a voice channel.")
    if not voice_client.is_playing():
        return await interaction.response.send_message("Nothing is currently playing.")
    voice_client.pause()
    await interaction.response.send_message("Playback paused!")

# --- Resume ---
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client is None:
        return await interaction.response.send_message("I'm not in a voice channel.")
    if not voice_client.is_paused():
        return await interaction.response.send_message("I'm not paused right now.")
    voice_client.resume()
    await interaction.response.send_message("Playback resumed!")

# --- Stop ---
async def stop(interaction: discord.Interaction):
    await interaction.response.defer()
    voice_client = interaction.guild.voice_client
    if not voice_client or not voice_client.is_connected():
        await interaction.followup.send("I'm not connected to any voice channel.")
        return
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
    await interaction.followup.send("Stopped playback and disconnecting...")
    asyncio.create_task(voice_client.disconnect())

# --- Play ---
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer(ephemeral=True)
    voice_client = interaction.guild.voice_client
    voice_channel = interaction.user.voice.channel
    if interaction.user.voice is None or interaction.user.voice.channel is None:
        await interaction.followup.send("You must be in a voice channel.", ephemeral=True)
        return
    if voice_client is None:
        voice_client = await voice_channel.connect()
        await voice_client.guild.change_voice_state(channel=voice_client.channel, self_deaf=True)
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    ydl_options = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'extract_flat': False,
        'default_search': 'ytsearch',
        'cookiefile': 'cookies.txt',
    }

    query = "ytsearch1:" + song_query
    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get("entries", [])
    if not tracks:
        await interaction.followup.send("No results found.")
        return

    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "Untitled")
    author = first_track.get("uploader", "Unknown")
    duration_sec = first_track.get("duration")
    duration = f"{duration_sec//60}:{duration_sec%60:02d}" if duration_sec else None
    thumbnail = first_track.get("thumbnail")

    guild_id = str(interaction.guild_id)
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()
    SONG_QUEUES[guild_id].append((audio_url, title, author, duration, thumbnail))
    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f"Added to queue: **{title}**")
    else:
        await interaction.followup.send(f"Now playing: **{title}**")
        await play_next_song(voice_client, guild_id, interaction.channel)

# --- QUEUE ---
async def queue(interaction: Interaction):
    guild_id = str(interaction.guild_id)
    queue = SONG_QUEUES.get(guild_id)
    if not queue or len(queue) == 0:
        await interaction.response.send_message("🎵 The queue is empty.", ephemeral=True)
        return
    lines = [f"**{i+1}.** {truncate(title, 50)}" for i, (_, title, _, _, _) in enumerate(queue)]
    embed = discord.Embed(title="🎵 Queue", description="\n".join(lines), color=discord.Color.green())
    await interaction.response.send_message(embed=embed)
