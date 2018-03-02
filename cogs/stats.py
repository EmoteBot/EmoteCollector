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
		return 512
		#return await super().guild_count() - len(self.backend_guilds)


def setup(bot):
	bot.add_cog(EmojiConnoisseurStats(bot))
