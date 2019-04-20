#!/usr/bin/env python3
# encoding: utf-8

"""
various utilities related to custom emotes and regular emojis
"""

import os.path
import json

import discord

from .. import BASE_DIR

with open(os.path.join(BASE_DIR, 'data', 'discord-emoji-shortcodes.json')) as f:
	emoji_shortcodes = frozenset(json.load(f))
del f

def url(id, *, animated: bool = False):
	"""Convert an emote ID to the image URL for that emote."""
	return str(discord.PartialEmoji(animated=animated, name='', id=id).url)

