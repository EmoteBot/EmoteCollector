#!/usr/bin/env python3
# encoding: utf-8

"""
Various utilities for use in discord.py bots.

Constants:

SUCCESS_EMOTES -- index it with True or False to get an emote indicating success or failure.

Classes:

EmojiConnoisseurContext: a generic context which extends discord.ext.commands.Context.
LRUDict: an extension of lru.LRU to add a pop method.

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
import re as _re

from aiohttp import ClientSession as _ClientSession
import discord as _discord
from discord.ext import commands as _commands
from lru import LRU as _LRUDict


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


async def create_gist(filename, contents: str):
	"""Upload a single file to Github Gist. Multiple files Never™"""
	async with _session.post(
		'https://api.github.com/gists',
		data=_json.dumps({
			'public': False,
			'files': {
				filename: {
					'content': contents}}})) as resp:
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
	"""An extension of lru.LRU to add `pop`"""

	_sentinel = object()

	def __init__(self, limit):
		self._dict = _LRUDict(limit)

	def __delitem__(self, key):
		del self._dict[key]

	def __getitem__(self, key):
		return self._dict[key]

	def __setitem__(self, key, value):
		self._dict[key] = value

	def get(self, key, default):
		"""L.get(key, default) -> If L has key return its value, otherwise default"""
		return self._dict.get(key, default)

	def pop(self, key, default=_sentinel):
		"""Needed for LRUDicts, which cannot be extended because lru-dict is written in C."""
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
				self._dict.update(d)
			else:
				for k, v in d:
					# lru.LRU doesn't support this, although dict does
					self[k] = v

		self._dict.update(kwargs)

	def set_callback(self, callback):
		"""L.set_callback(callback) -> set a callback to call when an item is evicted.
		The callback will receive (key, value) as args.
		"""
		self._dict.set_callback(callback)

	def set_size(self, size):
		"""L.set_size(size) -> set the new maximum number of entries for this LRUDict."""
		self._dict.set_size(size)

	def peek_first_item(self):
		"""L.peek_first_item() -> returns the MRU item (key,value) without changing key order"""
		return self._dict.peek_first_item()

	def peek_last_item(self):
		"""L.peek_first_item() -> returns the LRU item (key,value) without changing key order"""
		return self._dict.peek_last_item()

	def get_size(self):
		"""Return the maximum number of entries for this LRUDict."""
		return self._dict.get_size()

	def get_stats(self):
		"""L.get_stats() -> returns a tuple with cache hits and misses"""
		return self._dict.get_stats()

	def clear(self):
		"""remove all entries"""
		self._dict.clear()

	def __iter__(self):
		yield from iter(self._dict)

	def __repr__(self):
		return f'{self.__class__.__name__}({self.__dict__!r})'

	def __str__(self):
		return str(self._dict)

	def __sizeof__(self):
		return self._dict.__sizeof__

	def __len__(self):
		return len(self._dict)

	def __eq__(self, other):
		return self._dict == other

	def __ne__(self, other):
		return self._dict != other

	def keys(self):
		"""L.keys() -> list of L's keys in descending recently used order"""
		return self._dict.keys()

	def values(self):
		"""L.values() -> list of L's values in descending recently used order"""
		return self._dict.values()

	def items(self):
		"""L.items() -> list of L's items (key, value) in descending recently used order"""
		return self._dict.items()

	def __contains__(self, key):
		return key in self._dict
