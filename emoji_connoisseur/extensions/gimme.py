import asyncio
import contextlib
import logging

import discord
from discord.ext import commands

from .. import utils
from .db import DatabaseEmote

logger = logging.getLogger(__name__)

class Gimme:
	guilds = frozenset()

	def __init__(self, bot):
		self.bot = bot

	@commands.command()
	async def gimme(self, context, emote: DatabaseEmote):
		"""Lets you join the server that has the emote you specify.

		If you have nitro, this will let you use it anywhere!
		"""

		guild = self.bot.get_guild(emote.guild)
		invite = await guild.text_channels[0].create_invite(
			max_age=600,
			max_uses=2,
			reason=_('Created for {user}').format(
				user=utils.format_user(self.bot, context.author, mention=False)))

		try:
			await context.author.send(_(
				'Invite to the server that has {emote}: {invite.url}').format(**locals()))
		except discord.Forbidden:
			await context.send(_('Unable to send invite in DMs. Please allow DMs from server members.'))
		else:
			with contextlib.suppress(discord.HTTPException):
				await context.message.add_reaction('📬')

	async def on_message(self, message):
		if message.guild in self.guilds:
			await asyncio.sleep(5)
			await message.delete()

	async def on_backend_guild_enumeration(self, guilds):
		self.guilds = guilds
		await self.delete_all_backend_guild_messages()

	async def delete_all_backend_guild_messages(self):
		# ensure there's no messages left over from last run
		for guild in self.guilds:
			permissions = guild.default_role.permissions
			permissions.send_messages = True
			await guild.default_role.edit(permissions=permissions)

			channel = guild.text_channels[0]
			name = channel.name
			await guild.create_text_channel(name=name)

			for channel in guild.text_channels:
				await channel.delete()

		logger.info('all backend guilds cleared')

def setup(bot):
	bot.add_cog(Gimme(bot))
