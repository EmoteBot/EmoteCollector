#!/usr/bin/env python3
# encoding: utf-8

import os.path

from discord.ext import commands

from .. import BASE_DIR
from .. import utils

MEMES_FILE = os.path.join(BASE_DIR, 'data', 'memes.py')

class Meme:
	def __init__(self, bot):
		self.bot = bot
		self.read_memes_task = self.bot.loop.create_task(self.read_memes())

	def __unload(self):
		self.read_memes_task.cancel()

	async def read_memes(self):
		with open(MEMES_FILE) as f:
			self.memes = utils.load_json_compat(f.read())

	@commands.command(hidden=True)
	async def meme(self, context, *, name):
		response = self.memes.get(name)
		if response is not None:
			await context.send(utils.fix_first_line(response))


def setup(bot):
	import os.path

	if os.path.isfile(MEMES_FILE):
		bot.add_cog(Meme(bot))
