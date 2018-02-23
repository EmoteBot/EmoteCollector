# encoding: utf-8

from .external.stats import Stats


class EmojiConnoisseurStats(Stats):
	@property
	def guild_count(self):
		emoji_cog = self.bot.get_cog('Emoji')
		# fallback in case the emotes cog hasn't been loaded yet or its on_ready hasn't run yet
		backend_guild_count = 0 if emoji_cog is None else len(emoji_cog.guilds)
		return super().guild_count - backend_guild_count


def setup(bot):
	bot.add_cog(EmojiConnoisseurStats(bot))
