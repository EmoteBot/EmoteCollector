#!/usr/bin/env python3.6
# encoding: utf-8

import json

import aiofiles
from discord.ext import commands


class Memes:
	def __init__(self, bot):
		self.bot = bot
		self.bot.loop.create_task(self.read_memes())

	async def read_memes(self):
		async with aiofiles.open('data/memes.json') as f:
			self.memes = json.loads(await f.read())

	@commands.command(hidden=True)
	async def meme(self, context, name):
		response = self.memes.get(name)
		if response is not None:
			await context.send(response)


def setup(bot):
	bot.add_cog(Memes(bot))
