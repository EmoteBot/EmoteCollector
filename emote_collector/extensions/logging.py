# Emote Collector collects emotes from other servers for use by people without Nitro
# Copyright © 2018–2019 lambda#0987
#
# Emote Collector is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Emote Collector is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Emote Collector. If not, see <https://www.gnu.org/licenses/>.

import asyncio
import datetime
import logging

import discord
from discord.ext import commands

from .. import utils

logger = logging.getLogger(__name__)

class LogColor:  # like an enum but we don't want the conversion of fields to instances of the enum type
	__slots__ = ()

	_discord_color = lambda *hsv: discord.Color.from_hsv(*(component / 100 for component in hsv))

	white = _discord_color(0, 0, 100)
	black = _discord_color(0, 0, 0)
	green = _discord_color(33.6, 56.3, 68.4)
	dark_green = _discord_color(33.2, 39.1, 64.5)
	red = _discord_color(0.8, 48.8, 100)
	light_red = _discord_color(0.8, 48.8, 78.1)
	dark_red = _discord_color(0.8, 77.34, 95.3)
	gray = _discord_color(55.1, 30.5, 54.3)
	grey = gray

	add = dark_green
	preserve = green
	remove = red
	force_remove = dark_red
	unpreserve = light_red
	nsfw = white
	sfw = black
	decay = gray

	del _discord_color

LogColour = LogColor

# based on code provided by Pandentia
# https://gitlab.com/Pandentia/element-zero/blob/dbc695bc9ea7ba2a553e26db1f5fabcba600ef98/element_zero/util/logging.py
# Copyright © 2017–2018 Pandentia

class Logger(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.channels = {}
		self.configured = asyncio.Event()
		self.task = self.bot.loop.create_task(self.init_channels())

	def cog_unload(self):
		self.task.cancel()

	async def init_channels(self):
		await self.bot.wait_until_ready()
		if self.configured.is_set():
			return

		for channel_id, settings in self.bot.config['logs'].items():
			channel = self.bot.get_channel(channel_id)
			if channel is None:
				logger.warning(f'Configured logging channel ID {channel_id} was not found!')
			if isinstance(channel, discord.VoiceChannel):
				logger.warning(f'Voice channel {channel!r} was configured as a logging channel!')
				continue
			self.channels[channel] = settings

		self.configured.set()

	async def _log(self, *, event, nsfw, embed):
		await self.configured.wait()  # don't let people bypass logging by taking actions before logging is set up

		async def send(channel):
			try:
				return await channel.send(embed=embed)
			except discord.HTTPException as exception:
				logging.error(f'Sending a log ({embed}) to {channel!r} failed:')
				logging.error(utils.format_http_exception(exception))

		await asyncio.gather(*(
			send(channel)
			for channel, settings
			in self.channels.items()
			if
				(not nsfw or settings.get('include_nsfw_emotes', False))
				and event in settings['actions']))

	async def log_emote_action(self, *, event, emote, title=None, by: discord.User = None):
		e = discord.Embed()
		author = utils.format_user(self.bot, emote.author, mention=True)
		e.description = (
			f'{emote.with_linked_name(separator="—")}\n'
			f'Owner: {author}')
		if by:
			e.description += f'\nAction taken by: {by.mention}'

		e.set_footer(text='Emote originally created')
		e.timestamp = emote.created
		e.color = getattr(LogColor, event)
		e.title = title or event.title()

		await self._log(event=event, nsfw=emote.is_nsfw, embed=e)

	@commands.Cog.listener()
	async def on_emote_add(self, emote):
		await self.log_emote_action(event='add', emote=emote)

	@commands.Cog.listener()
	async def on_emote_remove(self, emote):
		await self.log_emote_action(event='remove', emote=emote)

	@commands.Cog.listener()
	async def on_emote_decay(self, emote):
		await self.log_emote_action(event='decay', emote=emote)

	@commands.Cog.listener()
	async def on_emote_force_remove(self, emote, responsible_moderator: discord.User):
		await self.log_emote_action(
			event='force_remove',
			emote=emote,
			title='Removal by a moderator',
			by=responsible_moderator)

	@commands.Cog.listener()
	async def on_emote_preserve(self, emote):
		await self.log_emote_action(event='preserve', emote=emote, title='Preservation')

	@commands.Cog.listener()
	async def on_emote_unpreserve(self, emote):
		await self.log_emote_action(event='unpreserve', emote=emote, title='Un-preservation')

	@commands.Cog.listener()
	async def on_emote_nsfw(self, emote, responsible_moderator: discord.User = None):
		await self.log_emote_action(event='nsfw', emote=emote, title='Marked NSFW', by=responsible_moderator)

	@commands.Cog.listener()
	async def on_emote_sfw(self, emote, responsible_moderator: discord.User = None):
		await self.log_emote_action(event='sfw', emote=emote, title='Marked SFW', by=responsible_moderator)

def setup(bot):
	bot.add_cog(Logger(bot))
