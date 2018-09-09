#!/usr/bin/env python3
# encoding: utf-8

import os.path

from . import EmoteCollector, BASE_DIR
from . import utils

with open(os.path.join(BASE_DIR, 'data', 'config.py')) as f:
	config = utils.load_json_compat(f.read())

bot = EmoteCollector(config=config)
bot.run()
