# encoding: utf-8

from .external.stats import Stats


class EmojiConnoisseurStats(Stats):
	@property
	def guild_count(self):
		emoji_cog = self.bot.get_cog('Emoji')
		return super().guild_count - len(emoji_cog.guilds)


def setup(bot):
	bot.add_cog(EmojiConnoisseurStats(bot))
