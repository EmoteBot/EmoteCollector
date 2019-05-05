import asyncio
import contextlib
import logging

import discord
from discord.ext import commands

from .. import utils
from ..utils.converter import DatabaseEmoteConverter

logger = logging.getLogger(__name__)

class Gimme(commands.Cog):
	guilds = frozenset()

	def __init__(self, bot):
		self.bot = bot
		self.db_cog = self.bot.get_cog('Database')
		self._init_task = self.bot.loop.create_task(self._init())

	async def cog_unload(self):
		self._init_task.cancel()

	@commands.command()
	async def gimme(self, context, emote: DatabaseEmoteConverter(check_nsfw=False)):
		"""Lets you join the server that has the emote you specify.

		If you have nitro, this will let you use it anywhere!
		"""

		guild = self.bot.get_guild(emote.guild)
		invite = await guild.text_channels[0].create_invite(
			max_age=600,
			max_uses=2,
			reason='Created for {user}'.format(
				user=utils.format_user(self.bot, context.author, mention=False)))

		try:
			await context.author.send(_(
				'Invite to the server that has {emote}: {invite.url}').format(**locals()))
		except discord.Forbidden:
			await context.send(_('Unable to send invite in DMs. Please allow DMs from server members.'))
		else:
			with contextlib.suppress(discord.HTTPException):
				await context.message.add_reaction('📬')

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild in self.guilds:
			await asyncio.sleep(5)
			with contextlib.suppress(discord.HTTPException):
				await message.delete()

	async def _init(self):
		await self.db_cog.have_guilds.wait()
		self.guilds = self.db_cog.guilds
		await self.delete_backend_guild_messages()

	async def delete_backend_guild_messages(self):
		# ensure there's no messages left over from last run
		for guild in self.guilds:
			permissions = guild.default_role.permissions
			permissions.send_messages = True
			await guild.default_role.edit(permissions=permissions)

			for channel in guild.text_channels:
				await channel.delete()

			await guild.create_text_channel(name='just-created-so-i-can-invite-you')

		logger.info('all backend guild text channels have been cleared')

def setup(bot):
	bot.add_cog(Gimme(bot))
