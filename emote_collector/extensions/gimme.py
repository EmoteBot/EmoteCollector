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
import contextlib
import logging

import discord
from discord.ext import commands

from .. import utils
from ..utils import ObjectProxy
from ..utils.converter import DatabaseEmoteConverter

logger = logging.getLogger(__name__)

class Gimme(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.guilds = ObjectProxy(lambda: bot.cogs['Database'].guilds)
		self.task = self.bot.loop.create_task(self.delete_backend_guild_messages())

	def cog_unload(self):
		self.task.cancel()

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

	@commands.Cog.listener(name='on_ready')
	async def delete_backend_guild_messages(self):
		# ensure there's no messages left over from last run
		for guild in self.guilds:
			await self.clear_guild(guild)
		logger.info('all backend guild text channels have been cleared')

	@commands.Cog.listener(name='on_backend_guild_join')
	async def clear_guild(self, guild):
		permissions = guild.default_role.permissions
		permissions.mention_everyone = False
		await guild.default_role.edit(permissions=permissions)

		for channel in guild.text_channels:
			with contextlib.suppress(discord.HTTPException):
				await channel.delete()

		await guild.create_text_channel(name='just-created-so-i-can-invite-you')

def setup(bot):
	bot.add_cog(Gimme(bot))
