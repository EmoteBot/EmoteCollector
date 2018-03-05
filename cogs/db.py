#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import logging
import random
import sys

import asyncpg

from ..utils import errors


logger = logging.getLogger('db')


class Database:
	def __init__(self, bot):
		self.bot = bot
		# not using create_task because we want the database to complete loading
		# only after the db is initialized
		self.bot.loop.run_until_complete(_get_db())
		# however, backend guild enumeration can wait
		# without it, the bot will report all guilds being full
		self.bot.loop.create_task(self.find_backend_guilds())

	@staticmethod
	def format_emote(emote: asyncpg.Record):
		animted = emote['animated']
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
			raise NoMoreSlotsError('This bot too weak! Try adding more guilds.')

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
		return await self.db.execute("""
			INSERT INTO user_opt (id, blacklist_reason) VALUES ($1, $2)
			ON_CONFLICT (id) DO UPDATE SET blacklisted = EXCLUDED.blacklisted""", user_id, reason)

	async def get_emote(self, name):
		return await self.db.fetchrow('SELECT * FROM emojis WHERE name ILIKE $1', name)

	async def get_formatted_emote(self, name):
		return self.format_emote(await self.get_emote(name))

	async def get_emotes(self, author_id=None):
		"""return an async iterator that gets emotes from the database.
		If author id is provided, get only emotes from them."""
		query = 'SELECT * FROM emojis '
		args = []
		if author_id is not None:
			query += 'WHERE author = $1 '
			args.append(author_id)
		query += 'ORDER BY LOWER(name)'

		async with self.db.acquire() as connection:
			async with connection.transaction():
				return connection.cursor(query, *args)

	async def exists_check(self, name):
		"""fail with an exception if an emote called `name` already exists.
		this is to reduce duplicated exception raising code."""
		if await self.get_emote(name) is None:
			raise errors.EmoteNotFoundError(name)

	async def create_emote(self, name, author_id, animated, image_data: bytes):
		blacklist_reason = self.get_user_blacklist(author_id)
		if blacklist_reason:
			raise errors.UserBlacklisted(blacklist_reason)
		await self.exists_check(name)

		# checks passed
		guild = self.free_guild(animated)

		emote = await guild.create_custom_emoji(name=name, image=image_data)
		await self.db.execute(
			'INSERT INTO emojis(name, id, author, animated) VALUES ($1, $2, $3, $4)',
			name, emote.id, author_id, animated)

		return await self.get_emote(name)

	async def is_owner(self, name, user_id):
		"""return whether the user has permissions to modify this emote"""
		emote = await self.get(name)
		user = discord.Object(user_id)
		return await self.bot.is_owner(user) or emote['author'] == user.id

	async def owner_check(self, name, user_id):
		"""like is_owner but fails with an exception if the user is not authorized.
		this is to reduce duplicated exception raising code."""
		await self.exists_check(name)
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
		# don't fail if new_name is a different capitalization of old_name
		if old_name.lower() != new_name.lower():
			await self.exists_check(new_name)
		await self.owner_check(old_name, user_id)
		db_emote = await self.get_emote(old_name)
		emote = self.bot.get_emoji(db_emote['id'])
		await emote.edit(name=new_name)
		await self.db.execute('UPDATE emojis SET name = $2 where id = $1', id, new_name)

	async def set_emote_description(self, name, description=None, user_id):
		"""Set an emote's description. It will be shown in ec/info.

		If you leave out the description, it will be removed.
		You could use this to:
		- Detail where you got the image
		- Credit another author
		- Write about why you like the emote
		- Describe how it's used

		There's a 500 character limit currently.
		"""
		await self.is_owner_check(name, user_id)
		try:
			await self.bot.db.execute(
				'UPDATE emojis SET DESCRIPTION = $2 WHERE NAME ILIKE $1',
				name,
				description)
		# wowee that's a verbose exception name
		# like why not just call it "StringTooLongError"?
		except asyncpg.StringDataRightTruncationError as exception:
			raise errors.EmoteDescriptionTooLong from exception

	async def toggle_user_state(self, user_id):
		# TODO
		...

	async def toggle_guild_state(self, guild_id):
		# TODO
		...

	async def get_user_state(self, user_id):
		return await self.db.fetchval(
			'SELECT COALESCE(state, FALSE) FROM user_opt WHERE id = $1',
			user_id)

	async def get_guild_state(self, guild_id):
		"""return whether this guild is opt in"""
		return await self.db.fetchval(
			'SELECT COALESCE(state, FALSE) FROM guild_opt WHERE id = $1',
			guild_id)

	async def get_state(self, guild_id, user_id):
		state = True

		guild_state = await self.get_guild_state(guild_id)
		if guild_state is not None:
			state = guild_state

		user_state = await self.get_user_state(user_id)
		if user_state is not None:
			state = user_state  # user state overrides guild state

		return state

	async def _get_db(self):
		credentials = self.bot.config['database']

		try:
			db = await asyncpg.create_pool(**credentials)
		except ConnectionRefusedError as exception:
			logger.error('%s: %s', type(exception).__name__, exception)
			sys.exit(1)

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
		await db.execute('CREATE TABLE IF NOT EXISTS connoisseur.blacklists(id bigint NOT NULL UNIQUE)')
		return db


DB = asyncio.get_event_loop().run_until_complete(_get_db())
