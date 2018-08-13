#!/usr/bin/env python3
# encoding: utf-8

import re


"""
various utilities related to custom emotes
"""

"""Matches custom server emotes."""
RE_CUSTOM_EMOTE = re.compile(r'<(?P<animated>a?):(?P<name>\w{2,32}):(?P<id>\d{17,})>', re.ASCII)

def url(id, *, animated: bool = False):
	"""Convert an emote ID to the image URL for that emote."""
	extension = 'gif' if animated else 'png'
	return f'https://cdn.discordapp.com/emojis/{id}.{extension}?v=1'
