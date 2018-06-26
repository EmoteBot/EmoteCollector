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

from collections import OrderedDict
from datetime import datetime
from functools import wraps
from typing import Sequence, Union

import asyncio
from asyncpg import Record
import discord
from discord.ext import commands
import discord.utils
from lru import LRU as _LRUDict	 # sunder only because we are defining our own, better LRUDict
from prettytable import PrettyTable
from wrapt import ObjectProxy

from cogs.utils import Utils  # note: we would like access to some functions that *are* hot-reloadable
from . import checks
from . import errors
from . import paginator


def load_json_compat(data: str):
	"""evaluate a python dictionary/list/thing, while maintaining compatibility with JSON"""
	# >HOLD UP! Why the heck are you using eval in production??
	# Short answer: JSON sucks for a configuration format:
	# 	It can be hard to read
	# 	Only one type of quote is allowed
	# 	No trailing commas are allowed
	# 	No multi-line strings
	# 	But most importantly, NO COMMENTS!
	# >OK but you didn't answer my question
	# Well I would use another configuration language, but they all suck.
	# To really answer your question, the config file is 100% trusted data.
	# NOTHING the user ever sends, ends up in there.
	# Furthermore, the if the user ever does get a hold of the config.py file,
	# then they already have the bot token and have totally compromised the bot.
	globals = dict(true=True, false=False, null=None)
	return eval(data, globals)


async def async_enumerate(async_iterator, start=0):
	i = int(start)
	async for x in async_iterator:
		yield i, x
		i += 1


class HistoryMessage(commands.Converter):
	@classmethod
	async def convert(cls, context, argument):
		# ID conversion
		try:
			offset_or_id = int(argument)
		except ValueError:
			pass
		else:
			if offset_or_id > 21154535154122752:  # smallest known snowflake
				return await _cls.get_message(id)
			elif offset_or_id < 0:  # it's an offset
				utils_cog = context.bot.get_cog('Utils')
				# skip the invoking message
				return await utils_cog.get_message(context.channel, offset_or_id - 1)

		async for message in context.history():
			if message.id == context.message.id:
				continue  # skip the invoking message
			if argument.casefold() in message.content.casefold():
				return message

		raise commands.BadArgument('Message not found.')

	@staticmethod
	async def _get_message(id):
		try:
			return await context.channel.get_message(id)
		except discord.NotFound:
			raise commands.BadArgument(
				'Message not found! Make sure your message ID is correct.') from None
		except discord.Forbidden:
			raise commands.BadArgument(
				'Permission denied! Make sure the bot has permission to read that message.') from None


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

		if rows:
			super().__init__(rows[0].keys(), **options)
		else:
			super().__init__()
		# PrettyTable's constructor does not set this property for some reason
		self.align = options.get('align', 'l')  # left align

		for row in rows:
			self.add_row(row)


class CustomContext(commands.Context):
	"""A custom context for discord.py which adds some utility functions."""

	async def try_add_reaction(self,
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
		# if func is a method, args starts with (self, context, ...)
		# otherwise args starts with (context, ...)
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

		if kwargs:
			self.update(kwargs)
