#!/usr/bin/env python3
# encoding: utf-8

import re


"""
various utilities related to custom emotes
"""

"""Matches :foo: and ;foo; but not :foo;. Used for emotes in text."""
RE_EMOTE = re.compile(r'(:|;)(?P<name>\w{2,32})\1|(?P<newline>\n)', re.ASCII)

"""Matches \:foo: and \;foo;, allowing one to prevent the emote auto response for one emote."""
# we don't need to match :foo\:, since "foo\" is not a valid emote name anyway
RE_ESCAPED_EMOTE = re.compile(r'\\(:|;)\w{2,32}\1')

"""Matches only custom server emotes."""
RE_CUSTOM_EMOTE = re.compile(r'<(?P<animated>a?):(?P<name>\w{2,32}):(?P<id>\d{17,})>', re.ASCII)

def url(id, *, animated: bool = False):
	"""Convert an emote ID to the image URL for that emote."""
	extension = 'gif' if animated else 'png'
	return f'https://cdn.discordapp.com/emojis/{id}.{extension}?v=1'
