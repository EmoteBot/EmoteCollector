#!/usr/bin/env python3
# encoding: utf-8

from functools import wraps as _wraps
import random as _random
import sys as _sys

from discord.ext.commands import Context as _Context


"""More owners, other than Emoji Backend 0. If more backend accounts are needed, add them here."""
EXTRA_OWNERS = (140516693242937345,)


async def is_owner(context):
	user = context.author
	return user.id in EXTRA_OWNERS or await context.bot.is_owner(user)


class MockContext(_Context):
	async def mock(self, content, **kwargs):
		def mock(char):
			return _random.choice((str.upper, str.lower))(char)
		return await self.send(''.join(map(mock, content)) + ' <:SpongeMock:407348053129822208>', **kwargs)


def typing(func):
	@_wraps(func)
	async def wrapped(context, *args, **kwargs):
		async with context.sleeping():
			await func(context, *args, **kwargs)
	return wrapped


def log(*args, **kwargs):
	kwargs['file'] = _sys.stderr
	print(*args, **kwargs)
