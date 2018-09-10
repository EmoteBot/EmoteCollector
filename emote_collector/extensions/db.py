#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import contextlib
import datetime
import logging
import random
import re
import time

import asyncpg
import discord
from discord.ext import commands

from .. import utils
from ..utils import errors

logger = logging.getLogger(__name__)

class DatabaseEmote(utils.AttrDict):
	def __hash__(self):
		return self.id >> 22

	def __str__(self):
		animated = 'a' if self.animated else ''
		return '<{0}:{1.name}:{1.id}>'.format(animated, self)

	def as_reaction(self):
		"""return this emote as a string suitable for passing to Message.add_reaction"""
		# apparently "a:" is not necessary for animated emote reactions
		return f':{self.name}:{self.id}'

	def escaped_name(self):
		"""return the emote's name in colons, suitable for displaying how to use the emote
		or when the emote no longer exists."""
		# \ in case they name an emote, e.g. :grinning:
		# we want to display :grinning:, not 😁
		return fr'\:{self.name}:'

	def with_name(self):
		"""return this emote as a string suitable for displaying in a list form or embed"""
		return f'{self} ({self.escaped_name()})'

	@property
	def url(self):
		return utils.emote.url(self.id, animated=self.animated)

	@classmethod
	async def convert(cls, context, name: str):
		name = name.strip().strip(':;')
		cog = context.bot.get_cog('Database')
		return await cog.get_emote(name)

class Database:
	def __init__(self, bot):
		self.bot = bot
		self._pool = self.bot.pool
		self.tasks = []
		# without backend guild enumeration, the bot will report all guilds being full
		self.tasks.append(self.bot.loop.create_task(self.find_backend_guilds()))
		self.tasks.append(self.bot.loop.create_task(self.update_emote_guilds()))
		self.tasks.append(self.bot.loop.create_task(self.decay_loop()))
		self.logger = self.bot.get_cog('Logger')

	def __unload(self):
		for task in self.tasks:
			task.cancel()

	async def find_backend_guilds(self):
		"""Find all the guilds used to store emotes"""

		if getattr(self, 'guilds', None):
			return

		await self.bot.wait_until_ready()

		guilds = set()
		for guild in self.bot.guilds:
			if (
				guild.name.startswith(('EmojiBackend', 'EmoteBackend'))
				and await self.bot.is_owner(guild.owner)
			):
				guilds.add(guild)

		await self._pool.executemany("""
			INSERT INTO _guilds
			VALUES ($1)
			ON CONFLICT (id) DO NOTHING
		""", map(lambda x: (x.id,), guilds))

		self.guilds = frozenset(guilds)
		logger.info('In %s backend guilds.', len(self.guilds))

		# allow other cogs that depend on the list of backend guilds to know when they've been found
		self.bot.dispatch('backend_guild_enumeration', self.guilds)

	async def update_emote_guilds(self):
		"""update the guild column in the emotes table

		it's null in a former installation without the guild column
		"""

		emotes = []
		async for db_emote in self.all_emotes():
			discord_emote = self.bot.get_emoji(db_emote.id)
			if discord_emote is None:
				continue
			emotes.append((db_emote.id, discord_emote.guild_id))

		await self._pool.executemany('UPDATE emotes SET guild = $2 WHERE id = $1', emotes)

	async def decay_loop(self):
		while True:
			logger.debug('entering decay loop')
			if not self.bot.config.get('decay', False):
				logger.warning('decay disabled! make sure it\'s enabled in the config.')
				return
			logger.debug('decay enabled')

			await self.bot.wait_until_ready()
			await self.bot.db_ready.wait()
			logger.debug('decaying')

			await self.decay()

			await asyncio.sleep(60*10)

	@commands.command(name='sql', aliases=['SQL'], hidden=True)
	@commands.is_owner()
	async def sql_command(self, context, *, query):
		"""Gets the rows of a SQL query. Prepared statements are not supported."""
		start = time.monotonic()
		# XXX properly strip codeblocks
		try:
			results = await self._pool.fetch(query.strip('`'))
		except asyncpg.PostgresError as exception:
			return await context.send(exception)
		elapsed = time.monotonic() - start

		message = await utils.codeblock(str(utils.PrettyTable(results)))
		return await context.send(f'{message}*{len(results)} rows retrieved in {elapsed:.2f} seconds.*')

	async def free_guild(self, animated=False):
		"""Find a guild in the backend guilds suitable for storing an emote.

		As the number of emotes stored by the bot increases, the probability of finding a rate-limited
		guild approaches 1, but until then, this should work pretty well.
		"""

		# random() hopefully lets us bypass emote rate limits
		# otherwise if we always pick the first available gulid,
		# we might reuse it often and get rate limited.
		guild_id = await self._pool.fetchval(f"""
			SELECT id
			FROM guilds
			WHERE {'animated' if animated else 'static'}_usage < 50
			ORDER BY random()
			LIMIT 1
		""")

		if guild_id is None:
			raise errors.NoMoreSlotsError

		return guild_id

		guild = self.bot.get_guild(guild_id)
		if guild is None:
			raise errors.DiscordError('free backend guild retrieved from database but not in client cache')

		return guild

	## Informational

	async def count(self) -> asyncpg.Record:
		"""Return (not animated count, animated count, total)"""
		return await self._pool.fetchrow("""
			SELECT
				COUNT(*) FILTER (WHERE NOT animated) AS static,
				COUNT(*) FILTER (WHERE animated) AS animated,
				COUNT(*) AS total
			FROM emotes;""")

	def capacity(self):
		"""return a three-tuple of static capacity, animated, total"""
		return (len(self.guilds)*50,)*2+(len(self.guilds)*50*2,)

	async def get_emote(self, name) -> DatabaseEmote:
		"""get an emote object by name"""
		# we use LOWER(name) = LOWER($1) instead of ILIKE because ILIKE has some wildcarding stuff
		# that we don't want
		# probably LOWER(name) = $1, name.lower() would also work, but this looks cleaner
		# and keeps the lowercasing behavior consistent
		result = await self._pool.fetchrow('SELECT * FROM emotes WHERE LOWER(name) = LOWER($1)', name)
		if result:
			return DatabaseEmote(result)
		else:
			raise errors.EmoteNotFoundError(name)

	async def get_emote_usage(self, emote) -> int:
		"""return how many times this emote was used"""
		return await self._pool.fetchval(
			'SELECT COUNT(*) FROM emote_usage_history WHERE id = $1',
			emote.id)

	## Iterators

	def all_emotes(self, author_id=None):
		"""return an async iterator that gets emotes from the database.
		If author id is provided, get only emotes from them."""
		query = 'SELECT * FROM emotes '
		args = []
		if author_id is not None:
			query += 'WHERE author = $1 '
			args.append(author_id)
		query += 'ORDER BY LOWER(name)'

		return self._database_emote_cursor(query, *args)

	def popular_emotes(self, *, limit=200):
		"""return an async iterator that gets emotes from the db sorted by popularity"""
		query = """
			SELECT *, (
				SELECT COUNT(*)
				FROM emote_usage_history
				WHERE id = emotes.id
				AND time > (CURRENT_TIMESTAMP - INTERVAL '4 weeks')
			) AS usage
			FROM emotes
			ORDER BY usage DESC, LOWER("name")
			LIMIT $1
		"""
		return self._database_emote_cursor(query, limit)

	def search(self, substring):
		"""return an async iterator that gets emotes from the db whose name contains `substring`."""

		query = """
			SELECT *
			FROM emotes
			WHERE str_contains(LOWER($1), LOWER(name))
			ORDER BY LOWER(name) ASC
		"""
		return self._database_emote_cursor(query, substring)

	def decayable_emotes(self, cutoff: datetime = None, usage_threshold=2):
		"""emotes that should be removed due to inactivity.

		returns an async iterator over all emotes that:
			- were created before `cutoff`, and
			- have been used < `usage_threshold` between now and cutoff, and
			- are not preserved

		the default cutoff is 4 weeks.
		"""
		if cutoff is None:
			cutoff = datetime.datetime.utcnow() - datetime.timedelta(weeks=4)

		return self._database_emote_cursor("""
			SELECT *
			FROM emotes
			WHERE (
				SELECT COUNT(*)
				FROM emote_usage_history
				WHERE
					id = emotes.id
					AND time > $1
			) < $2
			AND NOT preserve
			AND created < $1;
		""", cutoff, usage_threshold)

	async def _database_emote_cursor(self, query, *args):
		"""like _cursor, but wraps results in DatabaseEmote objects"""

		async for row in self._cursor(query, *args):
			yield DatabaseEmote(row)

	async def _cursor(self, query, *args):
		"""return an Async Generator over all records selected by the query and its args"""

		async with self._pool.acquire() as connection:
			async with connection.transaction():
				async for row in connection.cursor(query, *args):
					# we can't just return connection.cursor(...)
					# because the connection would be closed by the time we returned
					# so we have to become a generator to keep the conn open
					yield row

	## Checks

	async def ensure_emote_does_not_exist(self, name):
		"""fail with an exception if an emote called `name` does not exist
		this is to reduce duplicated exception raising code."""

		try:
			emote = await self.get_emote(name)
		except errors.EmoteNotFoundError:
			pass
		else:
			raise errors.EmoteExistsError(emote)

	async def is_owner(self, emote, user_id):
		"""return whether the user has permissions to modify this emote"""

		if user_id is None:
			return True

		if not emote:  # you can't own an emote that doesn't exist
			raise errors.EmoteNotFoundError(name)
		user = discord.Object(user_id)
		return await self.bot.is_owner(user) or emote.author == user.id

	async def owner_check(self, emote, user_id):
		"""like is_owner but fails with an exception if the user is not authorized.
		this is to reduce duplicated exception raising code."""
		if not await self.is_owner(emote, user_id):
			raise errors.PermissionDeniedError(emote.name)

	## Actions

	async def create_emote(self, name, author_id, animated, image_data: bytes):
		await self.ensure_emote_does_not_exist(name)

		guild_id = await self.free_guild(animated)

		image = discord.utils._bytes_to_base64_data(image_data)
		emote_data = await self.bot.http.create_custom_emoji(guild_id=guild_id, name=name, image=image)
		return DatabaseEmote(await self._pool.fetchrow("""
			INSERT INTO emotes(name, id, author, animated, guild)
			VALUES ($1, $2, $3, $4, $5)
			RETURNING *""", name, int(emote_data['id']), author_id, animated, guild_id))

	async def remove_emote(self, emote, user_id):
		"""Remove an emote given by name.
		- user_id: the user trying to remove this emote,
		  or None if their ownership should not
		  be verified

		returns the emote that was deleted
		"""
		if isinstance(emote, str):
			emote = await self.get_emote(name=emote)

		await self.owner_check(emote, user_id)

		await self.bot.http.delete_custom_emoji(emote.guild, emote.id)
		await self._pool.execute('DELETE FROM emotes WHERE id = $1', emote.id)
		return emote

	async def rename_emote(self, old_name, new_name, user_id):
		"""rename an emote from old_name to new_name. user_id must be authorized."""

		# don't fail if new_name is a different capitalization of old_name
		if old_name.lower() != new_name.lower():
			await self.ensure_emote_does_not_exist(new_name)

		emote = await self.get_emote(old_name)
		await self.owner_check(emote, user_id)

		await self.bot.http.edit_custom_emoji(emote.guild, emote.id, name=new_name)
		return DatabaseEmote(await self._pool.fetchrow("""
			UPDATE emotes
			SET name = $2
			WHERE id = $1
			RETURNING *""", emote.id, new_name))

	async def set_emote_description(self, name, user_id=None, description=None):
		"""Set an emote's description.

		If you leave out the description, it will be removed.
		You could use this to:
		- Detail where you got the image
		- Credit another author
		- Write about why you like the emote
		- Describe how it's used
		"""
		emote = await self.get_emote(name)
		await self.owner_check(emote, user_id)

		try:
			return DatabaseEmote(await self._pool.fetchrow("""
				UPDATE emotes
				SET DESCRIPTION = $2
				WHERE id = $1
				RETURNING *""",emote.id, description))
		# wowee that's a verbose exception name
		# like why not just call it "StringTooLongError"?
		except asyncpg.StringDataRightTruncationError as exception:
			# XXX dumb way to do it but it's the only way i've got
			limit = int(re.search(r'character varying\((\d+)\)', exception.message)[1])
			raise errors.EmoteDescriptionTooLongError(emote.name, limit)

	async def set_emote_preservation(self, name, should_preserve: bool):
		"""change the preservation status of an emote.
		if an emote is preserved, it should not be decayed due to lack of use
		"""
		emote = await self._pool.fetchrow("""
			UPDATE emotes
			SET preserve = $1
			WHERE LOWER(name) = LOWER($2)
			RETURNING *""", should_preserve, name)

		# why are we doing this "if not emote" checking, when we could just call get_emote
		# before insert?
		# because that would constitute an extra database query which we don't need
		if not emote:
			raise errors.EmoteNotFoundError(name)
		else:
			return DatabaseEmote(emote)

	async def log_emote_use(self, emote_id, user_id=None):
		await self._pool.execute("""
			INSERT INTO emote_usage_history (id)
			-- this is SELECT ... WHERE NOT EXISTS, not INSERT INTO ... WHERE NOT EXISTS
			-- https://stackoverflow.com/a/15710598
			SELECT ($1)
			WHERE NOT EXISTS (
				-- restrict emote logging to non-owners
				-- this should reduce some spam and stats-inflation
				SELECT * FROM emotes WHERE id = $1 AND author = $2)""",
			emote_id, user_id)

	async def decay(self, cutoff=None, usage_threshold=2):
		if cutoff is None:
			cutoff = datetime.datetime.utcnow() - datetime.timedelta(weeks=4)

		async for emote in self.decayable_emotes(cutoff, usage_threshold):
			logger.debug('decaying %s', emote.name)
			removal_message = await self.logger.on_emote_decay(emote)
			try:
				await self.remove_emote(emote, user_id=None)
			except (errors.ConnoisseurError, errors.DiscordError) as ex:
				logger.error('decaying %s failed due to %s', emote.name, ex)
				with contextlib.suppress(AttributeError):
					await removal_message.delete()

	## User / Guild Options

	async def _toggle_state(self, table_name, id, default):
		"""toggle the state for a user or guild. If there's no entry already, new state = default."""
		# see _get_state for why string formatting is OK here
		return await self._pool.fetchval(f"""
			INSERT INTO {table_name} (id, state) VALUES ($1, $2)
			ON CONFLICT (id) DO UPDATE SET state = NOT {table_name}.state
			RETURNING state
		""", id, default)

	async def toggle_user_state(self, user_id, guild_id=None) -> bool:
		"""Toggle whether the user has opted to use the emote auto response.
		If the user does not have an entry already:
			If the guild_id is provided and not None, the user's state is set to the opposite of the guilds'
			Otherwise, the user's state is set to False, since the default state is True.
		Returns the new state."""
		default = False
		guild_state = await self.get_guild_state(guild_id)
		if guild_state is not None:
			# if the auto response is enabled for the guild then toggling the user state should opt out
			default = not guild_state
		return await self._toggle_state('user_opt', user_id, default)

	async def toggle_guild_state(self, guild_id):
		"""Togle whether this guild is opt out.
		If this guild is opt in, the emote auto response will be disabled
		except for users that have opted in to it using `toggle_user_state`.
		Otherwise, the response will be on for all users except those that have opted out.
		"""
		return await self._toggle_state('guild_opt', guild_id, False)

	async def _get_state(self, table_name, id):
		# unfortunately, using $1 for table_name is a syntax error
		# however, since table name is always hardcoded input from other functions in this module,
		# it's ok to use string formatting here
		return await self._pool.fetchval(f'SELECT state FROM {table_name} WHERE id = $1', id)

	async def get_user_state(self, user_id):
		"""return this user's global preference for the emote auto response"""
		return await self._get_state('user_opt', user_id)

	async def get_guild_state(self, guild_id):
		"""return whether this guild is opt in"""
		return await self._get_state('guild_opt', guild_id)

	async def get_state(self, guild_id, user_id):
		# TODO investigate whether this obviates get_guild_state and get_user_state (probably does)
		return await self._pool.fetchval("""
			SELECT COALESCE(
				CASE WHEN (SELECT blacklist_reason FROM user_opt WHERE id = $2)
					IS NULL THEN NULL
					ELSE FALSE
				END,
				(SELECT state FROM user_opt  WHERE id = $2),
				(SELECT state FROM guild_opt WHERE id = $1),
				true
			)""",
		guild_id, user_id)

	## Blacklists

	async def get_user_blacklist(self, user_id):
		"""return a reason for the user's blacklist, or None if not blacklisted"""
		return await self._pool.fetchval('SELECT blacklist_reason from user_opt WHERE id = $1', user_id)

	async def set_user_blacklist(self, user_id, reason=None):
		"""make user_id blacklisted
		setting reason to None removes the user's blacklist"""
		# insert regardless of whether it exists
		# and if it does exist, update
		await self._pool.execute("""
			INSERT INTO user_opt (id, blacklist_reason) VALUES ($1, $2)
			ON CONFLICT (id) DO UPDATE SET blacklist_reason = EXCLUDED.blacklist_reason""",
		user_id, reason)

def setup(bot):
	bot.add_cog(Database(bot))
