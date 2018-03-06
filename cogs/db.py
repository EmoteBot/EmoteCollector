#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import logging
import random
import sys

import asyncpg
import discord

from utils import errors


logger = logging.getLogger('cogs.db')


class Database:
	def __init__(self, bot):
		self.bot = bot
		self.bot.loop.create_task(self._get_db())
		# without backend guild enumeration, the bot will report all guilds being full
		self.bot.loop.create_task(self.find_backend_guilds())

	def __unload(self):
		self.bot.loop.create_task(self.db.close())

	@staticmethod
	def format_emote(emote: asyncpg.Record):
		animated = emote['animated']
		name = emote['name']
		id = emote['id']
		return f"<{'a' if animated else ''}:{name}:{id}>"

	@staticmethod
	def emote_url(emote_id):
		"""Convert an emote ID to the image URL for that emote."""
		return f'https://cdn.discordapp.com/emojis/{emote_id}?v=1'

	async def find_backend_guilds(self):
		"""Find all the guilds used to store emotes"""

		if hasattr(self, 'guilds') and self.guilds:  # pylint: disable=access-member-before-definition
			return

		await self.bot.wait_until_ready()

		guilds = []
		for guild in self.bot.guilds:
			if await self.bot.is_owner(guild.owner) and guild.name.startswith('EmojiBackend'):
				guilds.append(guild)
		self.guilds = guilds
		logger.info('In ' + str(len(guilds)) + ' backend guilds.')

		# allow other cogs that depend on the list of backend guilds to know when they've been found
		self.bot.dispatch('backend_guild_enumeration', self.guilds)

	def free_guild(self, animated=False):
		"""Find a guild in the backend guilds suitable for storing an emote.

		As the number of emotes stored by the bot increases, the probability of finding a rate-limited
		guild approaches 1, but until then, this should work pretty well.
		"""
		free_guilds = []
		for guild in self.guilds:
			if sum(animated == emote.animated for emote in guild.emojis) < 50:
				free_guilds.append(guild)

		if not free_guilds:
			raise NoMoreSlotsError

		# hopefully this lets us bypass the rate limit more often, since emote rates are per-guild
		return random.choice(free_guilds)

	async def count(self) -> asyncpg.Record:
		"""Return (not animated count, animated count, total)"""
		return await self.db.fetchrow("""
			SELECT
				COUNT(*) FILTER (WHERE NOT animated) AS static,
				COUNT(*) FILTER (WHERE animated) AS animated,
				COUNT(*) AS total
			FROM emojis;
			""")

	async def get_user_blacklist(self, user_id):
		"""return a reason for the user's blacklist, or None if not blacklisted"""
		return await self.db.fetchval('SELECT blacklist_reason from user_opt WHERE id = $1', user_id)

	async def set_user_blacklist(self, user_id, reason=None):
		"""make user_id blacklisted :c"""
		# insert regardless of whether it exists
		# and if it does exist, update
		await self.db.execute("""
			INSERT INTO user_opt (id, blacklist_reason) VALUES ($1, $2)
			ON CONFLICT (id) DO UPDATE SET blacklist_reason = EXCLUDED.blacklist_reason""", user_id, reason)

	async def get_emote(self, name):
		return await self.db.fetchrow('SELECT * FROM emojis WHERE name ILIKE $1', name)

	async def get_formatted_emote(self, name):
		emote = await self.get_emote(name)
		if emote is None:
			raise errors.EmoteNotFoundError(name)

		return self.format_emote(emote)

	async def get_emotes(self, author_id=None):
		"""return an async iterator that gets emotes from the database.
		If author id is provided, get only emotes from them."""
		query = 'SELECT * FROM emojis '
		args = []
		if author_id is not None:
			query += 'WHERE author = $1 '
			args.append(author_id)
		query += 'ORDER BY LOWER(name)'

		# gee whiz, just look at all these indents!
		async with self.db.acquire() as connection:
			async with connection.transaction():
				async for row in connection.cursor(query, *args):
					yield row

	async def ensure_emote_exists(self, name):
		"""fail with an exception if an emote called `name` does not exist
		this is to reduce duplicated exception raising code."""
		if await self.get_emote(name) is None:
			raise errors.EmoteNotFoundError(name)

	async def ensure_emote_does_not_exist(self, name):
		"""fail with an exception if an emote called `name` does not exist
		this is to reduce duplicated exception raising code."""
		if await self.get_emote(name) is not None:
			raise errors.EmoteExistsError(name)

	async def create_emote(self, name, author_id, animated, image_data: bytes):
		blacklist_reason = await self.get_user_blacklist(author_id)
		if blacklist_reason:
			raise errors.UserBlacklisted(blacklist_reason)
		await self.ensure_emote_does_not_exist(name)

		# checks passed
		guild = self.free_guild(animated)

		emote = await guild.create_custom_emoji(name=name, image=image_data)
		await self.db.execute(
			'INSERT INTO emojis(name, id, author, animated) VALUES ($1, $2, $3, $4)',
			name, emote.id, author_id, animated)

		return await self.get_emote(name)

	async def is_owner(self, name, user_id):
		"""return whether the user has permissions to modify this emote"""
		await self.ensure_emote_exists(name)
		emote = await self.get_emote(name)
		user = discord.Object(user_id)
		return await self.bot.is_owner(user) or emote['author'] == user.id

	async def owner_check(self, name, user_id):
		"""like is_owner but fails with an exception if the user is not authorized.
		this is to reduce duplicated exception raising code."""
		if not await self.is_owner(name, user_id):
			raise errors.PermissionDeniedError(name)

	async def remove_emote(self, name, user_id):
		"""Remove an emote given by name.
		- user_id: the user trying to remove this emote"""
		await self.owner_check(name, user_id)
		db_emote = await self.get_emote(name)
		emote = self.bot.get_emoji(db_emote['id'])
		if emote is None:
			raise errors.DiscordError()

		await emote.delete()
		await self.db.execute('DELETE FROM emojis WHERE name ILIKE $1', name)

	async def rename_emote(self, old_name, new_name, user_id):
		"""rename an emote from old_name to new_name. user_id must be authorized."""
		await self.owner_check(old_name, user_id)
		# don't fail if new_name is a different capitalization of old_name
		if old_name.lower() != new_name.lower() and await self.get_emote(new_name) is not None:
			raise errors.EmoteExistsError(new_name)
		db_emote = await self.get_emote(old_name)
		emote = self.bot.get_emoji(db_emote['id'])
		await emote.edit(name=new_name)
		await self.db.execute('UPDATE emojis SET name = $2 where id = $1', emote.id, new_name)

	async def set_emote_description(self, name, user_id, description=None):
		"""Set an emote's description.

		If you leave out the description, it will be removed.
		You could use this to:
		- Detail where you got the image
		- Credit another author
		- Write about why you like the emote
		- Describe how it's used
		"""
		await self.owner_check(name, user_id)
		try:
			await self.db.execute(
				'UPDATE emojis SET DESCRIPTION = $2 WHERE NAME ILIKE $1',
				name,
				description)
		# wowee that's a verbose exception name
		# like why not just call it "StringTooLongError"?
		except asyncpg.StringDataRightTruncationError as exception:
			raise errors.EmoteDescriptionTooLong from exception

	async def log_emote_use(self, emote, guild_id, user_id):
		await self.db.execute(
			'INSERT INTO emote_usage_history (emote_id, guild_id, user_id) VALUES ($1, $2, $3)',
			emote['id'], guild_id, user_id)

	async def _toggle_state(self, table_name, id, default):
		"""toggle the state for a user or guild. If there's no entry already, new state = default."""
		# see _get_state for why string formatting is OK here
		await self.db.execute(f"""
			INSERT INTO {table_name} (id, state) VALUES ($1, $2)
			ON CONFLICT (id) DO UPDATE SET state = NOT {table_name}.state
		""", id, default)

	async def toggle_user_state(self, user_id, guild_id=None) -> bool:
		"""Toggle whether the user has opted to use the emote auto response.
		If the user does not have an entry already:
			If the guild_id is provided and not None, the user's state is set to the opposite of the guilds'
			Otherwise, the user's state is set to False, since the default state is True.
		Returns the new state."""
		default = False
		if guild_id is not None:
			guild_state = await self.get_guild_state(guild_id)
			if guild_state is not None:
				default = not guild_state
		await self._toggle_state('user_opt', user_id, default)
		return await self.get_user_state(user_id)

	async def toggle_guild_state(self, guild_id):
		"""Togle whether this guild is opt in.
		If this guild is opt in, the emote auto response will be disabled
		except for users that have opted in to it using `toggle_user_state`.
		Otherwise, the response will be on for all users except those that have opted out."""
		await self._toggle_state('guild_opt', guild_id, True)
		return await self.get_guild_state(guild_id)

	async def _get_state(self, table_name, id):
		# unfortunately, using $1 for table_name is a syntax error
		# however, since table name is always hardcoded input from other functions in this module,
		# it's ok to use string formatting here
		return await self.db.fetchval(f'SELECT state FROM {table_name} WHERE id = $1', id)

	async def get_user_state(self, user_id):
		"""return this user's global preference for the emoji auto response"""
		return await self._get_state('user_opt', user_id)

	async def get_guild_state(self, guild_id):
		"""return whether this guild is opt in"""
		return await self._get_state('guild_opt', guild_id)

	async def get_state(self, guild_id, user_id):
		state = True

		guild_state = await self.get_guild_state(guild_id)
		if guild_state is not None:
			state = not guild_state  # since True means opt in

		user_state = await self.get_user_state(user_id)
		if user_state is not None:
			state = user_state  # user state overrides guild state

		return state

	async def _get_db(self):
		credentials = self.bot.config['database']
		db = await asyncpg.create_pool(**credentials)

		await db.execute('SET TIME ZONE UTC')  # make sure timestamps are displayed correctly
		await db.execute('CREATE SCHEMA IF NOT EXISTS connoisseur')
		await db.execute("""
			CREATE TABLE IF NOT EXISTS emojis(
				name VARCHAR(32) NOT NULL,
				id BIGINT NOT NULL UNIQUE,
				author BIGINT NOT NULL,
				animated BOOLEAN DEFAULT FALSE,
				description VARCHAR(280),
				created TIMESTAMP WITH TIME ZONE DEFAULT (now() at time zone 'UTC'),
				modified TIMESTAMP WITH TIME ZONE)""")
		await db.execute("""
			-- https://stackoverflow.com/a/26284695/1378440
			CREATE OR REPLACE FUNCTION update_modified_column()
			RETURNS TRIGGER AS $$
			BEGIN
				IF row(NEW.*) IS DISTINCT FROM row(OLD.*) THEN
					NEW.modified = now() at time zone 'UTC';
					RETURN NEW;
				ELSE
					RETURN OLD;
				END IF;
			END;
			$$ language 'plpgsql';""")
		await db.execute('DROP TRIGGER IF EXISTS update_emoji_modtime ON emojis')
		await db.execute("""
			CREATE TRIGGER update_emoji_modtime
			BEFORE UPDATE ON emojis
			FOR EACH ROW EXECUTE PROCEDURE update_modified_column();""")
		await db.execute('DROP TABLE IF EXISTS blacklists')
		await db.execute("""
			CREATE TABLE IF NOT EXISTS user_opt(
				id BIGINT NOT NULL UNIQUE,
				state BOOLEAN,
				blacklist_reason VARCHAR(500))""")
		await db.execute("""
			CREATE TABLE IF NOT EXISTS guild_opt(
				id BIGINT NOT NULL UNIQUE,
				state BOOLEAN NOT NULL)""")
		self.db = db


def setup(bot):
	bot.add_cog(Database(bot))
