#!/usr/bin/env python3
# encoding: utf-8

from functools import wraps as _wraps
import json as _json

from aiohttp import ClientSession as _ClientSession
from discord.ext import commands
from lru import LRU as _LRUDict


session = _ClientSession()
_sentinel = object()


def typing(func):
	"""Makes a command function run with the context.typing() decorator.
	This will make the bot appear to be typing for until the command returns.
	While you can just wrap your entire code in `async with context.typing()`,
	this isn't ideal if you already have a lot of indents or a long function.
	Also, context.trigger_typing() works but only for 10 seconds.
	"""
	@_wraps(func)
	async def wrapped(*args, **kwargs):
		# if func is a method, args starts with self, context, ...
		# otherwise args starts with context, ...
		context = args[0] if isinstance(args[0], commands.Context) else args[1]
		async with context.typing():
			await func(*args, **kwargs)
	return wrapped


async def create_gist(filename, contents: str):
	"""Upload a single file to Github Gist. Multiple files Never™"""
	async with session.post(
		'https://api.github.com/gists',
		data=_json.dumps({
			'public': False,
			'files': {
				filename: {
					'content': contents}}})) as resp:
		if resp.status == 201:
			return _json.loads(await resp.text())['html_url']


class LRUDict:
	"""An extension of lru.LRU to add `pop`"""

	def __init__(self, limit):
		self._dict = _LRUDict(limit)

	def __getitem__(self, key):
		return self._dict[key]

	def __setitem__(self, key, value):
		self._dict[key] = value

	def get(self, key, default):
		return self._dict.get(key, default)

	def pop(self, key, default=_sentinel):
		"""Needed for LRUDicts, which cannot be extended because lru-dict is written in C."""
		if default is _sentinel and key not in self:
			raise KeyError(key)
		result = self[key]
		del self[key]
		return result

	def update(self, d):
		self._dict.update(d)

	def set_callback(self, cb):
		self._dict.set_callback(cb)

	def set_size(self, size):
		self._dict.set_size(size)

	def peek_first_item(self):
		return self._dict.peek_first_item()

	def peek_last_item(self):
		return self._dict.peek_last_item()

	def get_size(self):
		return self._dict.get_size()

	def get_stats(self):
		return self._dict.get_stats()

	def clear(self):
		self._dict.clear()

	def __iter__(self):
		yield from iter(self._dict)

	def __repr__(self):
		return f'{self.__class__.name__}({self.__dict__!r})'

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
		return self._dict.keys()

	def values(self):
		return self._dict.values()

	def items(self):
		return self._dict.items()

	def __contains__(self, key):
		return key in self._dict
