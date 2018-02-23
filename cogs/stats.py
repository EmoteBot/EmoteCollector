# encoding: utf-8

import asyncio

from .external.stats import Stats


class EmojiConnoisseurStats(Stats):
	async def guild_count(self):
		emote_cog = self.bot.get_cog('Emotes')
		while emote_cog is None or not hasattr(emote_cog, 'guilds'):
			await asyncio.sleep(0.1)
		return super().guild_count - len(emote_cog.guilds)


def setup(bot):
	bot.add_cog(EmojiConnoisseurStats(bot))
