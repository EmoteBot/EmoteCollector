# Emote Collector collects emotes from other servers for use by people without Nitro
# Copyright © 2019 lambda#0987
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

import contextlib
import functools
import inspect

import aiocontextvars
import asyncpg

__all__ = ('connection', 'optional_connection')

_connection = aiocontextvars.ContextVar('connection')
# make the interface a bit shorter
connection = lambda: _connection.get()
connection.set = _connection.set

def optional_connection(func):
	"""Decorator that acquires a connection for the decorated function if the contextvar is not set."""
	class pool:
		def __init__(self, pool):
			self.pool = pool
		async def __aenter__(self):
			try:
				# allow someone to call a decorated function twice within the same Task
				# the second time, a new connection will be acquired
				connection().is_closed()
			except (asyncpg.InterfaceError, LookupError):
				self.connection = conn = await self.pool.acquire()
				connection.set(conn)
				return conn
			else:
				return connection()
		async def __aexit__(self, *excinfo):
			with contextlib.suppress(AttributeError):
				await self.pool.release(self.connection)

	if inspect.isasyncgenfunction(func):
		@functools.wraps(func)
		async def inner(self, *args, **kwargs):
			async with pool(self.bot.pool) as conn:
				# this does not handle two-way async gens, but i don't have any of those either
				async for x in func(self, *args, **kwargs):
					yield x
	else:
		@functools.wraps(func)
		async def inner(self, *args, **kwargs):
			async with pool(self.bot.pool) as conn:
				return await func(self, *args, **kwargs)

	return inner
