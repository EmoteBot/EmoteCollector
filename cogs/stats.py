# encoding: utf-8

import asyncio

from .external.stats import Stats


class EmojiConnoisseurStats(Stats):
	async def guild_count(self):
		backend_guilds = await self.bot.wait_for('backend_guild_enumeration')
		return await super().guild_count() - len(backend_guilds)


def setup(bot):
	bot.add_cog(EmojiConnoisseurStats(bot))
