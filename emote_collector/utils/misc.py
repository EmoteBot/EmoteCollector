# Emote Collector collects emotes from other servers for use by people without Nitro
# Copyright © 2018–2019 lambda#0987
#
# Emote Collector is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Emote Collector is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Emote Collector. If not, see <https://www.gnu.org/licenses/>.

import asyncio
import collections
import contextlib
import datetime
import functools
import io
import math
import re
import time
import typing
from typing import Sequence, Union
import urllib.parse

import asyncpg
import discord
from discord.ext import commands

from . import errors

"""miscellaneous utility functions and constants"""

"""Stanislav#0001's user ID
This is useful to test whether a number is a snowflake:
if it's greater than this number, it probably is"""
SMALLEST_SNOWFLAKE = 21154535154122752

def bytes_to_int(x):
	return int.from_bytes(x, byteorder='big')

def int_to_bytes(n):
	num_bytes = int(math.ceil(n.bit_length() / 8))
	return n.to_bytes(num_bytes, byteorder='big')

def codeblock(message, *, lang=''):
	cleaned = message.replace('```', '\N{zero width space}'.join('```'))
	return f'```{lang}\n{cleaned}```'

async def get_message_by_offset(channel, index: int) -> discord.Message:
	"""Gets channel[-index]. For instance get_message(channel, -2) == second to last message.
	Requires channel history permissions
	"""
	m = None
	async for m in channel.history(limit=abs(index)):
		pass

	if not m:
		raise commands.BadArgument(_('Message not found.'))

	return m

def fix_first_line(message: str) -> str:
	"""In compact mode, prevent the first line from being misaligned because of the bot's username"""
	if '\n' in message:
		message = '\N{zero width space}\n' + message
	return message

def format_user(bot, id, *, mention=False):
	"""Format a user ID for human readable display."""
	user = bot.get_user(id)
	if user is None:
		return _('Unknown user with ID {id}').format(**locals())
	# not mention: @null byte#8191 (140516693242937345)
	# mention: <@140516693242937345> (null byte#8191)
	# this allows people to still see the username and discrim
	# if they don't share a server with that user
	if mention:
		return f'{user.mention} (@{user})'
	else:
		return f'@{user} ({user.id})'

def format_time(date: datetime.datetime):
	"""Format a datetime to look like '2018-02-22 22:38:12 UTC'."""
	return date.strftime('%Y-%m-%d %H:%m:%S %Z')

def strip_angle_brackets(string):
	"""Strip leading < and trailing > from a string.
	Useful if a user sends you a url like <this> to avoid embeds, or to convert emotes to reactions."""
	if string.startswith('<') and string.endswith('>'):
		return string[1:-1]
	return string

def format_http_exception(exception: discord.HTTPException):
	"""Formats a discord.HTTPException for relaying to the user.
	Sample return value:

	BAD REQUEST (status code: 400):
	Invalid Form Body
	In image: File cannot be larger than 256 kb.
	"""
	return (
		f'{exception.response.reason} (status code: {exception.response.status}):'
		f'\n{exception.text}')

def expand_cartesian_product(str) -> (str, str):
	"""expand a string containing one non-nested cartesian product strings into two strings

	>>> expand_cartesian_product('foo{bar,baz}')
	('foobar', 'foobaz')
	>>> expand_cartesian_product('{old,new}')
	('old', 'new')
	>>> expand_cartesian_product('uninteresting')
	('uninteresting', '')
	>>> expand_cartesian_product('{foo,bar,baz}')
	('foo,bar', 'baz')	# edge case that i don't need to fix

	"""

	match = re.search('{([^{}]*),([^{}]*)}', str)
	if match:
		return (
			_expand_one_cartesian_product(str, match, 1),
			_expand_one_cartesian_product(str, match, 2)
		)
	else:
		return (str, '')

def _expand_one_cartesian_product(str, match, group):
	return str[:match.start()] + match[group] + str[match.end():]

def load_json_compat(filename):
	"""evaluate a python dictionary/list/thing, while maintaining some compatibility with JSON"""
	# >HOLD UP! Why the heck are you using eval in production??
	# The config file is 100% trusted data.
	# NOTHING the user ever sends, ends up in there.
	# Also, consider another common approach: `import config`.
	# Which is arbitrary code execution anyway.
	# Also we add datetime to the globals so that we can use timedeltas in the config.
	globals = dict(true=True, false=False, null=None, datetime=datetime)
	with open(filename) as f:
		# we use compile so that tracebacks contain the filename
		compiled = compile(f.read(), filename, 'eval')

	return eval(compiled, globals)

async def async_enumerate(async_iterator, start=0):
	i = int(start)
	async for x in async_iterator:
		yield i, x
		i += 1

def size(data: typing.IO):
	"""return the size, in bytes, of the data a BytesIO object represents"""
	with preserve_position(data):
		data.seek(0, io.SEEK_END)
		return data.tell()

class preserve_position(contextlib.AbstractContextManager):
	def __init__(self, fp):
		self.fp = fp
		self.old_pos = fp.tell()

	def __exit__(self, *excinfo):
		self.fp.seek(self.old_pos)

def clean_content(bot, message, content, *, fix_channel_mentions=False, use_nicknames=True, escape_markdown=False):
	transformations = {}

	if fix_channel_mentions and message.guild:
		def resolve_channel(id, *, _get=message.guild.get_channel):
			ch = _get(id)
			return ('<#%s>' % id), ('#' + ch.name if ch else '#deleted-channel')

		transformations.update(resolve_channel(channel) for channel in message.raw_channel_mentions)

	if use_nicknames and message.guild:
		def resolve_member(id, *, _get=message.guild.get_member):
			m = _get(id)
			return '@' + m.display_name if m else '@deleted-user'
	else:
		def resolve_member(id, *, _get=bot.get_user):
			m = _get(id)
			return '@' + m.name if m else '@deleted-user'


	transformations.update(
		('<@%s>' % member_id, resolve_member(member_id))
		for member_id in message.raw_mentions
	)

	transformations.update(
		('<@!%s>' % member_id, resolve_member(member_id))
		for member_id in message.raw_mentions
	)

	if message.guild:
		def resolve_role(id, *, _find=discord.utils.find, _roles=message.guild.roles):
			r = _find(lambda x: x.id == id, _roles)
			return '@' + r.name if r else '@deleted-role'

		transformations.update(
			('<@&%s>' % role_id, resolve_role(role_id))
			for role_id in message.raw_role_mentions
		)

	def repl(match):
		return transformations.get(match[0], '')

	pattern = re.compile('|'.join(transformations.keys()))
	result = pattern.sub(repl, content)

	if escape_markdown:
		transformations = {
			re.escape(c): '\\' + c
			for c in ('*', '`', '_', '~', '\\')
		}

		def replace(match):
			return transformations.get(re.escape(match[0]), '')

		pattern = re.compile('|'.join(transformations.keys()))
		result = pattern.sub(replace, result)

	# Completely ensure no mentions escape:
	return re.sub(r'@(everyone|here|[!&]?[0-9]{17,21})', '@\u200b\\1', result)

def asyncexecutor(*, timeout=None):
	"""decorator that turns a synchronous function into an async one"""
	def decorator(func):
		@functools.wraps(func)
		def decorated(*args, **kwargs):
			f = functools.partial(func, *args, **kwargs)

			loop = asyncio.get_event_loop()
			coro = loop.run_in_executor(None, f)
			return asyncio.wait_for(coro, timeout=timeout, loop=loop)
		return decorated
	return decorator

async def timeit(coro, _timer=time.perf_counter):
	t0 = _timer()
	result = await coro
	t1 = _timer()
	return t1 - t0, result

def channel_is_nsfw(channel):
	return (
		not channel  # if not specified, allow NSFW
		or getattr(channel, 'nsfw', True))  # otherwise, allow NSFW if DMs or the guild channel is NSFW

def compose(*funcs):
	@functools.wraps(funcs[0])
	def f(x):
		for f in reversed(funcs):
			x = f(x)
		return x
	return f
