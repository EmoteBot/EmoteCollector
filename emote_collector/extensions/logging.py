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

import datetime
import logging

import discord
from discord.ext import commands

from .. import utils

logger = logging.getLogger(__name__)

class LogColor:  # like an enum but we don't want the conversion of fields to instances of the enum type
	__slots__ = ()

	_discord_color = lambda *hsv: discord.Color.from_hsv(*(component / 256 for component in hsv))

	green = _discord_color(86, 144, 175)
	dark_green = _discord_color(85, 100, 165)
	light_red = _discord_color(2, 125, 200)
	red = _discord_color(2, 125, 256)
	dark_red = _discord_color(2, 198, 244)
	gray = _discord_color(141, 78, 139)
	grey = gray

	add = dark_green
	preserve = green
	remove = red
	force_remove = dark_red
	unpreserve = light_red
	nsfw = light_red
	sfw = green
	decay = gray

	del _discord_color

LogColour = LogColor

# based on code provided by Pandentia
# https://gitlab.com/Pandentia/element-zero/blob/dbc695bc9ea7ba2a553e26db1f5fabcba600ef98/element_zero/util/logging.py
# Copyright © 2017–2018 Pandentia

class Logger(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.channel = None

		self.task = self.bot.loop.create_task(self.init_channel())
		self.init_settings()

	def cog_unload(self):
		self.task.cancel()

	async def init_channel(self):
		await self.bot.wait_until_ready()

		try:
			channel_id = self.bot.config['logs']['emotes']['channel']
		except KeyError:
			logger.warning('No logging channel was configured. Emote logging will not occur.')
			return

		self.channel = self.bot.get_channel(channel_id)

	def init_settings(self):
		self.settings = dict.fromkeys(
			(
				'add',
				'remove',
				'force_remove',
				'decay',
				'preserve',
				'unpreserve'),
			False)

		try:
			self.settings.update(self.bot.config['logs']['emotes']['settings'])
		except KeyError:
			logging.warning('emote logging has not been configured! emote logging will not take place')

	async def _log(self, **fields):
		footer = fields.pop('footer', None)
		fields.setdefault('timestamp', datetime.datetime.utcnow())

		e = discord.Embed(**fields)

		if footer:
			e.set_footer(text=footer)

		try:
			return await self.channel.send(embed=e)
		except AttributeError:
			# the channel isn't configured
			pass
		except discord.HTTPException as exception:
			logging.error(utils.format_http_exception(exception))

	async def log_emote_action(self, emote, action, color, *, by: discord.User = None):
		author = utils.format_user(self.bot, emote.author, mention=True)
		description = (
			f'{emote.with_linked_name(separator="—")}\n'
			f'Owner: {author}')
		if by:
			description += f'\nAction taken by: {by.mention}'

		footer = 'Emote originally created'
		timestamp = emote.created

		return await self._log(title=action, description=description, footer=footer, timestamp=timestamp, color=color)

	@commands.Cog.listener()
	async def on_emote_add(self, emote):
		if self.settings['add']:
			return await self.log_emote_action(emote, 'Add', LogColor.add)

	@commands.Cog.listener()
	async def on_emote_remove(self, emote):
		if self.settings['remove']:
			return await self.log_emote_action(emote, 'Remove', LogColor.remove)

	@commands.Cog.listener()
	async def on_emote_decay(self, emote):
		if self.settings['decay']:
			return await self.log_emote_action(emote, 'Decay', LogColor.decay)

	@commands.Cog.listener()
	async def on_emote_force_remove(self, emote, responsible_moderator: discord.User):
		if not self.settings['force_remove']:
			return

		return await self.log_emote_action(
			emote,
			'Removal by a moderator',
			LogColor.force_remove,
			by=responsible_moderator)

	@commands.Cog.listener()
	async def on_emote_preserve(self, emote):
		if self.settings['preserve']:
			await self.log_emote_action(emote, 'Preservation', LogColor.preserve)

	@commands.Cog.listener()
	async def on_emote_unpreserve(self, emote):
		if self.settings['unpreserve']:
			await self.log_emote_action(emote, 'Un-preservation', LogColor.unpreserve)

	@commands.Cog.listener()
	async def on_emote_nsfw(self, emote, responsible_moderator: discord.User):
		if self.settings.get('nsfw'):  # .get cause it's new
			await self.log_emote_action(emote, 'Marked NSFW', LogColor.nsfw, by=responsible_moderator)

	@commands.Cog.listener()
	async def on_emote_sfw(self, emote, responsible_moderator: discord.User):
		if self.settings.get('sfw'):
			await self.log_emote_action(emote, 'Marked SFW', LogColor.sfw, by=responsible_moderator)

def setup(bot):
	bot.add_cog(Logger(bot))
