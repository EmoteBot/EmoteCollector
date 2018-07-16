import colorsys
import datetime
import enum

import discord


def _hsv_to_discord_color(h, s, v):
	r,g,b = colorsys.hsv_to_rgb(h/255,s/255,v)
	print(r,g,b)
	return discord.Color.from_rgb(*map(int, (r,g,b)))

class LogColor:  # like an enum but we don't want the conversion of fields to the Enum type
	__slots__ = ()

	ADD = _hsv_to_discord_color(86, 144, 175)
	REMOVE = _hsv_to_discord_color(2, 198, 244)
	FORCE_REMOVE = REMOVE  # TODO pick a diff color (maybe darker red?)
	DECAY = _hsv_to_discord_color(141, 78, 139)

# based on code provided by Pandentia
# https://gitlab.com/Pandentia/element-zero/blob/dbc695bc9ea7ba2a553e26db1f5fabcba600ef98/element_zero/util/logging.py
# Copyright © 2017–2018 Pandentia

class Logger:

	def __init__(self, bot):
		self.bot = bot
		self.db = self.bot.get_cog('Database')
		self.utils = self.bot.get_cog('Utils')

		self.bot.loop.create_task(self.init_channel())
		self.init_settings()

	async def init_channel(self):
		await self.bot.wait_until_ready()

		self.channel = None

		try:
			channel_id = self.bot.config['logs']['emotes']['channel']
		except KeyError:
			return

		self.channel = self.bot.get_channel(channel_id)

	def init_settings(self):
		self.settings = dict(add=False, remove=False, force_remove=False, decay=False)

		try:
			self.settings.update(self.bot.config['logs']['emotes']['settings'])
		except KeyError:
			pass

	async def _log(self, **fields):
		footer = fields.pop('footer', None)

		e = discord.Embed(**fields)
		e.timestamp = datetime.datetime.utcnow()

		if footer:
			e.set_footer(text=footer)

		try:
			await self.channel.send(embed=e)
		except AttributeError:
			pass
		except discord.HTTPException:
			pass

	async def log_emoji_action(self, emote, action, color):
		author = self.utils.format_user(emote.author)
		description = f'{emote} - :{emote.name}:\nOwner: {author}'

		await self._log(title=action, description=description, color=color)

	async def log_emoji_add(self, emoji):
		if self.settings['add']:
			await self.log_emoji_action(emoji, 'Add', LogColor.ADD)

	async def log_emoji_remove(self, emoji):
		if self.settings['remove']:
			await self.log_emoji_action(emoji, 'Remove', LogColor.REMOVE)

	async def log_emoji_decay(self, emoji):
		if self.settings['decay']:
			await self.log_emoji_action(emoji, 'Decay', LogColor.DECAY)

	async def log_emoji_force_remove(self, emoji):
		if self.settings['force_remove']:
			await self.log_emoji_action(emoji, 'Removal by a moderator', LogColor.FORCE_REMOVE)


def setup(bot):
	bot.add_cog(Logger(bot))
