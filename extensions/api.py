#!/usr/bin/env python3
# encoding: utf-8

from discord.ext import commands

class API:
	def __init__(self, bot):
		self.bot = bot
		self.bot.loop.create_task(self._init())

	async def _init(self):
		db_cog = self.bot.get_cog('Database')
		await db_cog.ready.wait()
		self._pool = db_cog._pool

	@commands.group()
	async def api(self, context):
		"""Commands related to the Emoji Connoisseur API.

		This command on its own will tell you a bit about the API.
		"""

		await context.send(
			'I have a RESTful API available. The docs for it are located at '
			f'{self.bot.config["api"]["docs_url"]}')

def setup(bot):
	if bot.config.get('api'):
		bot.add_cog(API(bot))
