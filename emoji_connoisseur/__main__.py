#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import contextlib

from . import EmojiConnoisseur

loop = asyncio.get_event_loop()
bot = EmojiConnoisseur(loop=loop)

with contextlib.closing(loop):
	try:
		loop.run_until_complete(bot.start())
	finally:
		loop.run_until_complete(bot.logout())
