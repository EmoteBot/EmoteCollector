#!/usr/bin/env python3
# encoding: utf-8

"""
various utilities related to custom emotes
"""

def url(id, *, animated: bool = False):
	"""Convert an emote ID to the image URL for that emote."""
	extension = 'gif' if animated else 'png'
	return f'https://cdn.discordapp.com/emojis/{id}.{extension}?v=1'
