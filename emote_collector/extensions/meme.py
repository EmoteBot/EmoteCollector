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
		self.read_memes()

	def read_memes(self):
		self.memes = utils.load_json_compat(MEMES_FILE)

	@commands.command(hidden=True)
	async def meme(self, context, *, name):
		response = self.memes.get(name)
		if response is not None:
			await context.send(utils.fix_first_line(response))

def setup(bot):
	if os.path.isfile(MEMES_FILE):
		bot.add_cog(Meme(bot))
