#!/usr/bin/env python3
# encoding: utf-8

import os.path

from discord.ext import commands

from .. import BASE_DIR
from .. import utils

MEMES_FILE = os.path.join(BASE_DIR, 'data', 'memes.py')

class Meme(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.memes = utils.load_json_compat(MEMES_FILE)

	@commands.command(hidden=True)
	async def meme(self, context, *, name):
		try:
			await context.send(utils.fix_first_line(self.memes[name]))
		except KeyError:
			pass

def setup(bot):
	if os.path.isfile(MEMES_FILE):
		bot.add_cog(Meme(bot))
