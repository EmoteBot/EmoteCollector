#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import contextlib

from . import EmojiConnoisseur
from . import utils

loop = asyncio.get_event_loop()

with open('data/config.py') as f:
	config = utils.load_json_compat(f.read())

bot = EmojiConnoisseur(config=config, loop=loop)

with contextlib.closing(loop):
	try:
		loop.run_until_complete(bot.start())
	finally:
		loop.run_until_complete(bot.logout())
