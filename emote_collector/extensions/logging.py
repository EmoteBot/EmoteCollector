import colorsys
import datetime
import logging

import discord

from .. import utils

logger = logging.getLogger(__name__)

class LogColor:  # like an enum but we don't want the conversion of fields to instances of the enum type
	__slots__ = ()

	_discord_color = lambda h, s, v: discord.Color.from_hsv(*(component / 256 for component in (h, s, v)))

	green = _discord_color(86, 144, 175)
	dark_green = _discord_color(85, 100, 165)
	light_red = _discord_color(2, 125, 200)
	red = _discord_color(2, 125, 256)
	dark_red = _discord_color(2, 198, 244)
	gray = _discord_color(141, 78, 139)
	grey = gray

	add = green
	preserve = dark_green
	remove = red
	force_remove = dark_red
	unpreserve = light_red
	decay = gray

	del _discord_color

LogColour = LogColor

# based on code provided by Pandentia
# https://gitlab.com/Pandentia/element-zero/blob/dbc695bc9ea7ba2a553e26db1f5fabcba600ef98/element_zero/util/logging.py
# Copyright © 2017–2018 Pandentia

class Logger:
	def __init__(self, bot):
		self.bot = bot

		self.bot.loop.create_task(self.init_channel())
		self.init_settings()

	async def init_channel(self):
		await self.bot.wait_until_ready()

		self.channel = None

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

	async def log_emote_action(self, emote, action, color, *, extra=''):
		author = utils.format_user(self.bot, emote.author, mention=True)
		description = f'{emote.with_linked_name(separator="—")}\nOwner: {author}\n{extra}'
		footer = 'Emote originally created'
		timestamp = emote.created

		return await self._log(title=action, description=description, footer=footer, timestamp=timestamp, color=color)

	async def on_emote_add(self, emote):
		if self.settings['add']:
			return await self.log_emote_action(emote, 'Add', LogColor.add)

	async def on_emote_remove(self, emote):
		if self.settings['remove']:
			return await self.log_emote_action(emote, 'Remove', LogColor.remove)

	async def on_emote_decay(self, emote):
		if self.settings['decay']:
			return await self.log_emote_action(emote, 'Decay', LogColor.decay)

	async def on_emote_force_remove(self, emote, responsible_moderator: discord.User = None):
		if not self.settings['force_remove']:
			return

		extra = ''
		if responsible_moderator is not None:
			# we don't need to use format_user here because the moderator is in the same server as the log channel
			extra += f'Action taken by: {responsible_moderator.mention}'
		return await self.log_emote_action(emote, 'Removal by a moderator', LogColor.force_remove, extra=extra)

	async def on_emote_preserve(self, emote):
		if self.settings['preserve']:
			await self.log_emote_action(emote, 'Preservation', LogColor.preserve)

	async def on_emote_unpreserve(self, emote):
		if self.settings['unpreserve']:
			await self.log_emote_action(emote, 'Un-preservation', LogColor.unpreserve)

def setup(bot):
	bot.add_cog(Logger(bot))
