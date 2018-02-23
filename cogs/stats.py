# encoding: utf-8

from .external.stats import Stats

import time


class EmojiConnoisseurStats(Stats):
	async def guild_count(self):
		emoji_cog = self.bot.get_cog('Emoji')
		while emoji_cog is None or not hasattr(emoji_cog, 'guilds'):
			await asyncio.sleep(0.1)
		return super().guild_count - len(emoji_cog.guilds)


def setup(bot):
	bot.add_cog(EmojiConnoisseurStats(bot))
