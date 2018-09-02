#!/usr/bin/env python3
# encoding: utf-8

from . import EmojiConnoisseur
from . import utils

with open('data/config.py') as f:
	config = utils.load_json_compat(f.read())

bot = EmojiConnoisseur(config=config)
bot.run()
