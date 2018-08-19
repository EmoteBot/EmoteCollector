#!/usr/bin/env python3
# encoding: utf-8

import aiofiles
from discord.ext import commands

from .. import utils

MEMES_FILE = 'data/memes.py'

class Meme:
	def __init__(self, bot):
		self.bot = bot
		self.read_memes_task = self.bot.loop.create_task(self.read_memes())

	def __unload(self):
		self.read_memes_task.cancel()

	async def read_memes(self):
		async with aiofiles.open(MEMES_FILE) as f:
			self.memes = utils.load_json_compat(await f.read())

	@commands.command(hidden=True)
	async def meme(self, context, *, name):
		response = self.memes.get(name)
		if response is not None:
			await context.send(utils.fix_first_line(response))


def setup(bot):
	import os.path

	if os.path.isfile(MEMES_FILE):
		bot.add_cog(Meme(bot))
