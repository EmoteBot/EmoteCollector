#!/usr/bin/env python3
# encoding: utf-8

"""
various utilities related to custom emotes and regular emojis
"""

import os.path
import json

from .. import BASE_DIR

with open(os.path.join(BASE_DIR, 'data', 'discord-emoji-shortcodes.json')) as f:
	emoji_shortcodes = set(json.load(f))
del f

def url(id, *, animated: bool = False):
	"""Convert an emote ID to the image URL for that emote."""
	extension = 'gif' if animated else 'png'
	return f'https://cdn.discordapp.com/emojis/{id}.{extension}?v=1'
