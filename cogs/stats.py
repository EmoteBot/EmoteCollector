# encoding: utf-8

from .external.stats import Stats


class EmojiConnoisseurStats(Stats):
	@property
	def guild_count(self):
		emoji_cog = self.bot.get_cog('Emoji')
		# if the emoji cog hasn't finished running yet, emoji_cog will be None
		backend_guild_count = 100 if emoji_cog is None else len(emoji_cog.guilds)
		return super().guild_count - backend_guild_count


def setup(bot):
	bot.add_cog(EmojiConnoisseurStats(bot))
