import colorsys
import datetime
import enum

import discord


class LogColor:  # like an enum but we don't want the conversion of fields to the Enum type
	__slots__ = ()

	def _hsv_to_discord_color(h, s, v):
		r,g,b = colorsys.hsv_to_rgb(h/255,s/255,v)
		return discord.Color.from_rgb(*map(int, (r,g,b)))

	GREEN = _hsv_to_discord_color(86, 144, 175)
	LIGHT_GREEN = _hsv_to_discord_color(86, 144, 80)
	RED = _hsv_to_discord_color(2, 198, 244)
	DARK_RED = _hsv_to_discord_color(2, 125, 255)
	LIGHT_RED = _hsv_to_discord_color(2, 125, 200)
	GRAY = _hsv_to_discord_color(141, 78, 139)
	GREY = GRAY

	ADD = GREEN
	PRESERVE = LIGHT_GREEN
	REMOVE = RED
	FORCE_REMOVE = DARK_RED  # TODO pick a diff color (maybe darker red?)
	UNPRESERVE = LIGHT_RED
	DECAY = GRAY

	del _hsv_to_discord_color

LogColour = LogColor

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
		self.settings = dict.fromkeys(
			(
				'add',
				'remove',
				'force_remove',
				'decay',
				'preserve',
				'unpreserve',
			),
			False
		)
		dict(add=False, remove=False, force_remove=False, decay=False, preserve=False)

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
			return await self.channel.send(embed=e)
		except AttributeError:
			# the channel isn't configured
			pass
		except discord.HTTPException:
			pass

	async def log_emote_action(self, emote, action, color):
		author = self.utils.format_user(emote.author, mention=True)
		description = f'{emote} — :{emote.name}:\nOwner: {author}'

		return await self._log(title=action, description=description, color=color)

	async def on_emote_add(self, emote):
		if self.settings['add']:
			return await self.log_emote_action(emote, 'Add', LogColor.ADD)

	async def on_emote_remove(self, emote):
		if self.settings['remove']:
			return await self.log_emote_action(emote, 'Remove', LogColor.REMOVE)

	async def on_emote_decay(self, emote):
		if self.settings['decay']:
			return await self.log_emote_action(emote, 'Decay', LogColor.DECAY)

	async def on_emote_force_remove(self, emote):
		if self.settings['force_remove']:
			return await self.log_emote_action(emote, 'Removal by a moderator', LogColor.FORCE_REMOVE)

	async def on_emote_preserve(self, emote):
		if self.settings['preserve']:
			await self.log_emote_action(emote, 'Preservation', LogColor.PRESERVE)

	async def on_emote_unpreserve(self, emote):
		if self.settings['unpreserve']:
			await self.log_emote_action(emote, 'Un-preservation', LogColor.UNPRESERVE)


def setup(bot):
	bot.add_cog(Logger(bot))
