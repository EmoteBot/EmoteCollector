# encoding: utf-8

import asyncio
import math

from .external.stats import Stats


class EmojiConnoisseurStats(Stats):
	def __init__(self, bot):
		self.backend_guilds = []
		super().__init__(bot)

	async def on_backend_guild_enumeration(self, backend_guilds):
		self.backend_guilds = backend_guilds

	async def guild_count(self):
		guild_count = await super().guild_count() - len(self.backend_guilds)

		if math.log2(guild_count).is_integer():
			# TODO don't hardcode my user id, make it configurable as config['real_owner'] or simliar
			null_byte = self.bot.get_user(140516693242937345)
			await null_byte.send(f'Guild count ({guild_count}) is a power of 2!')

		return guild_count


def setup(bot):
	bot.add_cog(EmojiConnoisseurStats(bot))
