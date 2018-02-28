#!/usr/bin/env python3
# encoding: utf-8

"""
Various utilities for use in discord.py bots.

Constants:

SUCCESS_EMOTES -- index it with True or False to get an emote indicating success or failure.

Classes:

EmojiConnoisseurContext: a generic context which extends discord.ext.commands.Context.
LRUDict: an extension of lru.LRU to add a pop method, and support kwargs for the update method.

Functions:

typing: a decorator for discord.py commmands that sends a typing indicator to the invoking channel
until the command returns.
fix_first_line: takes in a list of lines and returns a fixed multi line message for compact mode users
create_gist: uploads text to gist.github.com
emote_url: given an ID of an emote, get the url which points to that emote's image
format_time: formats a datetime object to look like my preferred format
strip_angle_brackets: <http://foo.example> -> http://foo.example
"""


import asyncio as _asyncio
from datetime import datetime as _datetime
from functools import wraps as _wraps
import json as _json
import logging as _logging
import re as _re

from aiohttp import ClientSession as _ClientSession
import discord as _discord
from discord.ext import commands as _commands
from lru import LRU as _LRUDict
from wrapt import ObjectProxy as _ObjectProxy


_logger = _logging.getLogger('utils')  # i really need to start using __all__...
_session = _ClientSession(loop=_asyncio.get_event_loop())


"""Emotes used to indicate success/failure. You can obtain these from the discordbots.org guild,
but I uploaded them to my test server
so that both the staging and the stable versions of the bot can use them"""
SUCCESS_EMOTES = ('<:tickNo:416845770239508512>', '<:tickYes:416845760810844160>')


class CustomContext(_commands.Context):
	"""A custom context for discord.py which adds a few utility functions."""

	async def try_add_reaction(self, emoji, message=''):
		"""Try to add a reaction to the message. If it fails, send a message instead."""
		try:
			await self.message.add_reaction(strip_angle_brackets(emoji))
		except _discord.Forbidden:
			await self.send(f'{emoji} {message}')


def typing(func):
	"""Makes a command function run with the context.typing() decorator.
	This will make the bot appear to be typing for until the command returns.
	While you can just wrap your entire code in `async with context.typing()`,
	this isn't ideal if you already have a lot of indents or a long function.
	Also, context.trigger_typing() works but only for 10 seconds.
	"""
	@_wraps(func)
	async def wrapped(*args, **kwargs):  # pylint: disable=missing-docstring
		# if func is a method, args starts with self, context, ...
		# otherwise args starts with context, ...
		context = args[0] if isinstance(args[0], _commands.Context) else args[1]
		async with context.typing():
			await func(*args, **kwargs)
	return wrapped


def fix_first_line(lines: list) -> str:
	"""In compact mode, prevent the first line from being misaligned because of the bot's username"""
	if len(lines) > 1:
		lines[0] = '\N{zero width space}\n' + lines[0]
	return '\n'.join(lines)


async def create_gist(filename, contents: str, *, description=None):
	"""Upload a single file to Github Gist. Multiple files Never™"""
	_logger.debug('Attempting to post %s to Gist', filename)

	data = {
		'public': False,
		'files': {
			filename: {
				'content': contents}}}

	if description is not None:
		data['description'] = description

	async with _session.post('https://api.github.com/gists', data=_json.dumps(data)) as resp:
		if resp.status == 201:
			return _json.loads(await resp.text())['html_url']


def emote_url(emote_id):
	"""Convert an emote ID to the image URL for that emote."""
	return f'https://cdn.discordapp.com/emojis/{emote_id}?v=1'


def format_time(date: _datetime):
	"""Format a datetime to look like '2018-02-22 22:38:12 UTC'."""
	return date.strftime('%Y-%m-%d %H:%m:%S %Z')


def strip_angle_brackets(string):
	"""Strip leading < and trailing > from a string.
	Useful if a user sends you a url like <this> to avoid embeds, or to convert emotes to reactions."""
	if string.startswith('<') and string.endswith('>'):
		return string[1:-1]
	return string


class LRUDict:
	"""An extension of lru.LRU to add `pop` and fix `update`"""

	_sentinel = object()

	def __init__(self, size):
		super().__init__(_LRUDict(size))

	def pop(self, key, default=_sentinel):
		"""L.pop(k[,d]) -> v, remove specified key and return the corresponding value.
		If key is not found, d is returned if given, otherwise KeyError is raised
		"""
		if default is self._sentinel and key not in self:
			raise KeyError(key)
		result = self[key]
		del self[key]
		return result

	def update(self, d=None, **kwargs):
		"""L.update([d, ]**kwargs) -> None.  Update L from dict/iterable d and kwargs.
		If d is present and has a .keys() method, then does:  for k in d: L[k] = d[k]
		If d is present and lacks a .keys() method, then does:  for k, v in d: L[k] = v
		In either case, this is followed by: for k in kwargs:  L[k] = kwargs[k]
		"""
		if d is not None:
			if hasattr(d, 'keys'):
				self.__wrapped__.update(d)
			else:
				for k, v in d:
					# lru.LRU doesn't support this, although dict does
					self[k] = v

		if kwargs:  # prevent infinite recursion
			self.update(kwargs)
