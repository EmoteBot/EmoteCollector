#!/usr/bin/env python3.6
# encoding: utf-8

"""
Various utils that for whatever reason cannot or should not go in a cog
Most of the time, this is due to them being needed outside of cog scope, or accessible
without accessing Bot.

Note: try to put stuff in the Utils cog. Any code that goes in here requires a restart of the entire
bot in order to update. Any stuff that goes in Utils can be hot reloaded without downtime.
"""

__all__ = ('CustomContext', 'checks', 'errors', 'typing', 'LRUDict')


from functools import wraps
from typing import Sequence, Union

import asyncio
from asyncpg import Record
from collections import OrderedDict
import discord
from discord.ext import commands
from lru import LRU as _LRUDict	 # sunder only because we are defining our own, better LRUDict
from prettytable import PrettyTable
from wrapt import ObjectProxy as ObjectProxy

from cogs.utils import Utils  # note: we would like access to some functions that *are* hot-reloadable
from . import checks
from . import errors


class PrettyTable(PrettyTable):
	"""an extension of PrettyTable that works with asyncpg's Records and looks better"""
	def __init__(self, rows: Sequence[Union[Record, OrderedDict]], **options):
		defaults = dict(
			# super()'s default is ASCII | - +, which don't join seamlessly and look p bad
			vertical_char='│',
			horizontal_char='─',
			junction_char='┼')
		for option, default in defaults.items():
			options.setdefault(option, default)

		super().__init__(rows[0].keys(),
			**options)
		# PrettyTable's constructor does not set this property for some reason
		self.align = options.get('align', 'l')  # left align

		for row in rows:
			self.add_row(row)


class CustomContext(commands.Context):
	"""A custom context for discord.py which adds some utility functions."""

	async def try_add_reaction(
			self,
			emoji: discord.Emoji,
			message: discord.Message = None,
			fallback_message=''):
		"""Try to add a reaction to the message. If it fails, send a message instead."""
		if message is None:
			message = self.message

		try:
			await message.add_reaction(Utils.strip_angle_brackets(emoji))
		except discord.Forbidden:
			await self.send(f'{emoji} {message}')


def typing(func):
	"""Makes a command function run with the context.typing() decorator.
	This will make the bot appear to be typing for until the command returns.
	While you can just wrap your entire code in `async with context.typing()`,
	this isn't ideal if you already have a lot of indents or a long function.
	Also, context.trigger_typing() works but only for 10 seconds.
	"""
	@wraps(func)
	# TODO investigate whether wraps really works on asyncs (probably not).
	# Either way, `wrapt` provides a better @wraps, maybe that would work
	async def wrapped(*args, **kwargs):	 # pylint: disable=missing-docstring
		# if func is a method, args starts with self, context, ...
		# otherwise args starts with context, ...
		context = args[0] if isinstance(args[0], commands.Context) else args[1]
		async with context.typing():
			# XXX Currently there is a bug in context.typing, or maybe in the official Discord client
			# receiving a message *immediately* after a typing indicator
			# does not cancel the typing indicator.
			# By sleeping, we can work around that bug in case a command fails early.
			# This is also why this decorator should probably not be used
			# if you do not anticipate a command taking more than 10s.
			await asyncio.sleep(0.1)
			await func(*args, **kwargs)
	return wrapped


class LRUDict(ObjectProxy):
	"""An extension of lru.LRU to add `pop` and fix `update`"""

	_sentinel = object()  # used to detect when no argument is passed

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
		"""L.update([d, ]**kwargs) -> None.	 Update L from dict/iterable d and kwargs.
		If d is present and has a .keys() method, then does:  for k in d: L[k] = d[k]
		If d is present and lacks a .keys() method, then does:	for k, v in d: L[k] = v
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
