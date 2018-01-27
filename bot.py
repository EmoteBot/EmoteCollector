#!/usr/bin/env python3
# encoding: utf-8

import traceback
from pathlib import Path

import discord
from discord.ext import commands

from util import log
import db


class EmojiConnoisseur(commands.Bot):
	cogs_path = 'cogs'

	def __init__(bot, *args, **kwargs):
		bot.config = db.CONFIG
		bot.db = {
			'emojis': db.EMOJIS,
			'blacklists': db.BLACKLISTS}
		super().__init__(command_prefix=commands.when_mentioned_or('ec'), *args, **kwargs)

	async def on_ready(bot):
		separator = '━'
		messages = (
			'Logged in as: %s' % bot.user,
			'ID: %s' % bot.user.id)
		separator *= len(max(messages, key=len))
		log(separator, *messages, separator, sep='\n')

	def run(bot, *args, **kwargs):
		for extension in (p.stem for p in Path(bot.cogs_path).glob('*.py')):
			try:
				bot.load_extension(bot.cogs_path+'.'+extension)
			except Exception as e:
				log('Failed to load', extension)
				log(traceback.format_exc())
		super().run(bot.config['tokens']['discord'], *args, **kwargs)


# defined in a function so it can be run from a REPL if need be
def run():
	EmojiConnoisseur().run()


if __name__ == '__main__':
	run()
