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

import discord
from discord.ext import commands

from . import strip_angle_brackets

class CustomContext(commands.Context):
	"""A custom context for discord.py which adds some utility functions."""

	async def try_add_reaction(self,
		emoji: discord.Emoji,
		message: discord.Message = None,
		fallback_message=''
	):
		"""Try to add a reaction to the message. If it fails, send a message instead."""
		if message is None:
			message = self.message

		try:
			await message.add_reaction(strip_angle_brackets(emoji))
		except discord.Forbidden:
			await self.send(f'{emoji} {fallback_message}')
