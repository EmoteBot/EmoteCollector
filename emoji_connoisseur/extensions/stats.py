# encoding: utf-8

from ben_cogs.stats import Stats, setup


class Stats(Stats):
	def __init__(self, bot):
		self.backend_guilds = 0
		super().__init__(bot)

	async def on_backend_guild_enumeration(self, backend_guilds):
		self.backend_guilds = len(backend_guilds)

	async def guild_count(self):
		return await super().guild_count() - self.backend_guilds
