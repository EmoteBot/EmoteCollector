from discord.ext import commands

class Admin:
	async def __local_check(self, context):
		return await context.bot.is_owner(context.author)

	@commands.command(name='reload-emotes', hidden=True)
	async def reload_emotes(self, context):
		replies = context.bot.get_cog('Emotes').replies
		extension = 'emote_collector.extensions.emote'
		context.bot.unload_extension(extension)
		context.bot.load_extension(extension)
		context.bot.get_cog('Emotes').replies = replies
		# Translator's note: it's not crucial to translate this message, for the same reason as "Logger cog not loaded"
		await context.send(_('Reloaded the emotes extension with {} replies.').format(len(replies)))

def setup(bot):
	bot.add_cog(Admin())
