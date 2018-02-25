# encoding: utf-8

import asyncio
import math

from .external.stats import Stats


class EmojiConnoisseurStats(Stats):
	async def guild_count(self):
		backend_guilds = await self.bot.wait_for('backend_guild_enumeration')
		guild_count = await super().guild_count() - len(backend_guilds)

		if math.log2(guild_count).is_integer():
			# TODO don't hardcode my user id, make it configurable as config['real_owner'] or simliar
			null_byte = self.bot.get_user(140516693242937345)
			await null_byte.send(f'Guild count ({guild_count}) is a power of 2!')

		return guild_count


def setup(bot):
	bot.add_cog(EmojiConnoisseurStats(bot))
