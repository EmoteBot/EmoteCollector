import discord
from discord.ext import commands

from . import strip_angle_brackets

class CustomContext(commands.Context):
	"""A custom context for discord.py which adds some utility functions."""

	async def try_add_reaction(self,
		emoji: discord.Emoji,
		message: discord.Message = None,
		fallback_message=''):
		"""Try to add a reaction to the message. If it fails, send a message instead."""
		if message is None:
			message = self.message

		try:
			await message.add_reaction(strip_angle_brackets(emoji))
		except discord.Forbidden:
			await self.send(f'{emoji} {message}')
