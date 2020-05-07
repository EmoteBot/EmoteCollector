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
import contextlib
import datetime
import enum
import logging
import operator
import random
import re
import time
import typing

import asyncpg
import discord
from discord.ext import tasks, commands

from .. import utils
from ..utils import errors
from ..utils import image as image_utils
from ..utils.proxy import ObjectProxy

logger = logging.getLogger(__name__)

class PageDirection(enum.Enum):
	before = -1
	after = +1

class PageSpecifier:
	def __init__(self, direction, reference):
		self.direction = direction
		self.reference = reference

	def __repr__(self):
		return f'{type(self).__qualname__}({self.direction!r}, {self.reference!r})'

	def __eq__(self, other):
		return (
			isinstance(other, type(self))
			and self.direction is other.direction
			and self.reference == other.reference
		)

	# convenience factories

	@classmethod
	def first(cls):
		return cls(PageDirection.after, None)

	@classmethod
	def last(cls):
		return cls(PageDirection.before, None)

	@classmethod
	def after(cls, reference):
		return cls(PageDirection.after, reference)

	@classmethod
	def before(cls, reference):
		return cls(PageDirection.before, reference)

class MessageReplyType(enum.Enum):
	auto = 'AUTO'
	quote = 'QUOTE'

class DatabaseEmote:
	__slots__ = frozenset((
		'name',
		'id',
		'author',
		'animated',
		'description',
		'created',
		'modified',
		'preserve',
		'guild',
		'nsfw',
		'usage'))

	def __init__(self, record):
		for column in self.__slots__:
			with contextlib.suppress(KeyError):
				setattr(self, column, record[column])

	def __hash__(self):
		return self.id >> 22

	def __eq__(self, other):
		return self.id == other.id and isinstance(other, (type(self), discord.PartialEmoji, discord.Emoji))

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

	def linked_name(self):
		return f'[{self.escaped_name()}]({self.url})'

	def with_name(self):
		"""return this emote as a string suitable for displaying in a list form or embed"""
		return f'{self} {self.escaped_name()}'

	def with_linked_name(self, *, separator='|'):
		"""return this emote as a string suitable for displaying in a list form or embed"""
		return f'{self} {separator} {self.linked_name()}'

	def status(self):
		if self.preserve and self.is_nsfw:
			return _('(Preserved, NSFW)')
		if self.preserve and not self.is_nsfw:
			return _('(Preserved)')
		if not self.preserve and self.is_nsfw:
			return _('(NSFW)')
		return ''

	def with_status(self, *, linked=False):
		formatted = self.with_linked_name() if linked else self.with_name()
		return f'{formatted} {self.status()}'

	@property
	def url(self):
		return utils.emote.url(self.id, animated=self.animated)

	@property
	def is_nsfw(self):
		return self.nsfw.endswith('NSFW')

class Database(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self._process_decay_config()
		self.queries = self.bot.queries('emotes.sql')

		self.tasks = [
			self.bot.loop.create_task(meth()) for meth in (
				self.find_backend_guilds, self.leave_blacklisted_guilds)]
		self.tasks.append(self.decay_loop.start())

		self.logger = ObjectProxy(lambda: bot.cogs['Logger'])

		self.guild_ids = set()
		self.have_guilds = asyncio.Event()

	def _process_decay_config(self):
		# example: {'enabled': True, 'cutoff': {'time': datetime.timedelta(...), 'usage': 3}}
		decay_settings = self.bot.config.get('decay', False)
		if isinstance(decay_settings, bool):
			# old schema: just a bool to indicate enabled
			self.bot.config['decay'] = decay_settings = {'enabled': decay_settings}

		decay_settings.setdefault('enabled', False)

		cutoff_settings = decay_settings.setdefault('cutoff', {})
		cutoff_settings.setdefault('time', datetime.timedelta(weeks=4))
		cutoff_settings.setdefault('usage', 2)

	def cog_unload(self):
		for task in self.tasks:
			task.cancel()

	## Tasks

	async def find_backend_guilds(self):
		"""Find all the guilds used to store emotes"""
		if self.have_guilds.is_set():
			return

		await self.bot.wait_until_ready()

		guild_ids = {guild.id for guild in self.bot.guilds if self.is_backend_guild(guild)}

		self.guild_ids.update(guild_ids)
		self.have_guilds.set()
		await self.bot.pool.executemany(self.queries.add_guild(), ((id,) for id in self.guild_ids))

		logger.info('In %s backend guilds.', len(self.guilds))

		# allow other cogs that depend on the list of backend guilds to know when they've been found
		self.bot.dispatch('backend_guild_enumeration', self.guilds)

	@property
	def guilds(self):
		return {self.bot.get_guild(id) for id in self.guild_ids}

	def is_backend_guild(self, guild):
		return guild.owner_id in self.bot.config['backend_user_accounts']

	async def leave_blacklisted_guilds(self):
		await self.bot.wait_until_ready()
		async for guild in self.blacklisted_guilds():
			if type(guild) is int:
				continue
			await guild.leave()

	@tasks.loop(minutes=10.0)
	async def decay_loop(self):
		if not self.bot.config['decay']['enabled']:
			return

		await self.bot.wait_until_ready()
		await self.decay()

	## Events

	@commands.Cog.listener()
	async def on_guild_remove(self, guild):
		await self.bot.pool.execute(self.queries.delete_guild(), guild.id)
		with contextlib.suppress(AttributeError):
			self.guilds.discard(guild)

	@commands.Cog.listener()
	async def on_guild_join(self, guild):
		if self.is_backend_guild(guild):
			await self.bot.pool.execute(self.queries.add_guild(), guild.id)
			self.guilds.add(guild)
			self.bot.dispatch('backend_guild_join', guild)
		elif await self.get_guild_blacklist(guild.id):
			await guild.leave()

	## Informational

	async def free_guild(self, animated=False):
		"""Find a guild in the backend guilds suitable for storing an emote.

		As the number of emotes stored by the bot increases, the probability of finding a rate-limited
		guild approaches 1, but until then, this should work pretty well.
		"""

		# random() hopefully lets us bypass emote rate limits
		# otherwise if we always pick the first available gulid,
		# we might reuse it often and get rate limited.
		guild_id = await self.bot.pool.fetchval(self.queries.free_guild(animated))

		if guild_id is None:
			raise errors.NoMoreSlotsError

		return guild_id

	async def count(self) -> asyncpg.Record:
		"""Return (not animated count, animated count, total)"""
		return await self.bot.pool.fetchrow(self.queries.count())

	def capacity(self):
		"""return a three-tuple of static capacity, animated, total"""
		return (len(self.guilds) * 50,) * 2 + (len(self.guilds) * 50 * 2,)

	async def get_emote(self, name) -> DatabaseEmote:
		"""get an emote object by name"""
		# we use LOWER(name) = LOWER($1) instead of ILIKE because ILIKE has some wildcarding stuff
		# that we don't want
		# probably LOWER(name) = $1, name.lower() would also work, but this looks cleaner
		# and keeps the lowercasing behavior consistent
		result = await self.bot.pool.fetchrow(self.queries.get_emote(), name)
		if result:
			return DatabaseEmote(result)
		else:
			raise errors.EmoteNotFoundError(name)

	def get_emote_usage(self, emote) -> int:
		"""return how many times this emote was used"""
		cutoff_time = datetime.datetime.utcnow() - self.bot.config['decay']['cutoff']['time']
		return self.bot.pool.fetchval(self.queries.get_emote_usage(), emote.id, cutoff_time)

	async def get_reply_message(self, invoking_message):
		"""return a tuple of message_type, reply_message_id for the given invoking message ID
		or None, None if not found"""
		row = await self.bot.pool.fetchrow(self.queries.get_reply_message(), invoking_message)
		if row is None:
			return None, None

		return MessageReplyType(row['type']), row['reply_message']

	## Iterators

	# if a channel, acts based on whether the channel is NSFW
	# if a bool, allow NSFW emotes if True
	AllowNsfwType = typing.Union[discord.DMChannel, discord.TextChannel, bool]

	async def all_emotes(self, author_id=None, *, allow_nsfw: AllowNsfwType = False):
		"""return an async iterator that gets emotes from the database.
		If author id is provided, get only emotes from them.
		"""
		batch = await self.all_emotes_keyset(author_id, allow_nsfw=allow_nsfw)
		page = PageSpecifier.first()
		while batch:
			page.reference = batch[-1].name
			for emote in batch:
				yield emote
			batch = await self.all_emotes_keyset(author_id, allow_nsfw=allow_nsfw, page=page)

	async def all_emotes_keyset(
		self,
		author_id=None,
		*,
		allow_nsfw: AllowNsfwType = False,
		page: PageSpecifier = PageSpecifier.first(),
		limit: int = 100, debug=False
	):
		args = [self.allowed_nsfw_types(allow_nsfw)]

		sort_order = 'DESC' if page.direction is PageDirection.before else 'ASC'
		kwargs = dict(sort_order=sort_order)

		if page.reference is not None:
			args.append(page.reference)
		else:
			kwargs['end'] = True

		if author_id is not None:
			kwargs['filter_author'] = True
			args.append(author_id)

		args.append(min(max(limit, 1), 250))

		if debug:
			return self.queries.all_emotes_keyset(**kwargs), args

		results = list(map(DatabaseEmote, await self.bot.pool.fetch(
			self.queries.all_emotes_keyset(**kwargs),
			*args)))
		if page.direction is PageDirection.before:
			results.reverse()
		return results

	def popular_emotes(self, author_id=None, *, limit=200, allow_nsfw: AllowNsfwType = False):
		"""return an async iterator that gets emotes from the db sorted by popularity"""
		cutoff_time = datetime.datetime.utcnow() - self.bot.config['decay']['cutoff']['time']

		extra_args = [] if author_id is None else [author_id]
		return self._database_emote_cursor(
			self.queries.popular_emotes(filter_author=bool(extra_args)),
			cutoff_time, limit, self.allowed_nsfw_types(allow_nsfw), *extra_args)

	def search(self, query, *, allow_nsfw: AllowNsfwType = False):
		"""return an async iterator that gets emotes from the db whose name is similar to `query`."""
		return self._database_emote_cursor(self.queries.search(), query, self.allowed_nsfw_types(allow_nsfw))

	@classmethod
	def allowed_nsfw_types(cls, allow_nsfw: AllowNsfwType):
		"""return the allowed values for the nsfw column in an emote row based on the allow_nsfw argument.
		if it's a channel (any kind), return whether the channel is NSFW.
		else, return the argument.

		This is mostly useful for database functions which take in either a bool or channel and need to convert to
		something that can be passed into a SQL WHERE clause.
		"""
		if isinstance(allow_nsfw, (discord.DMChannel, discord.TextChannel)):
			allow_nsfw = utils.channel_is_nsfw(allow_nsfw)
		return ('SFW', 'SELF_NSFW', 'MOD_NSFW') if allow_nsfw else ('SFW',)

	def decayable_emotes(self):
		"""emotes that should be removed due to inactivity.

		returns an async iterator over all emotes that:
			- were created before `cutoff`, and
			- have been used < `usage_threshold` between now and cutoff, and
			- are not preserved

		the cut off and usage threshold are specified in a dict at self.bot.config['decay'],
		under subkeys 'cutoff_time' and 'cutoff_usage', respectively.
		"""
		cutoff_time = datetime.datetime.utcnow() - self.bot.config['decay']['cutoff']['time']
		usage_threshold = self.bot.config['decay']['cutoff']['usage']
		return self._database_emote_cursor(self.queries.decayable_emotes(), cutoff_time, usage_threshold)

	async def blacklisted_guilds(self):
		async for guild_id, in self._cursor(self.queries.blacklisted_guilds()):
			yield self.bot.get_guild(guild_id) or guild_id

	async def _database_emote_cursor(self, query, *args):
		"""like _cursor, but wraps results in DatabaseEmote objects"""
		async for row in self._cursor(query, *args):
			yield DatabaseEmote(row)

	async def _cursor(self, query, *args):
		"""return an Async Generator over all records selected by the query and its args"""

		async with self.bot.pool.acquire() as connection, connection.transaction():
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

	async def is_moderator(self, user_id):
		# check the set first to avoid a query
		# but also check the database in case we don't have access to the websocket and therefore the client cache
		return (
			await self.bot.is_owner(discord.Object(user_id))
			or await self.bot.pool.fetchval('SELECT true FROM moderators WHERE id = $1', user_id))

	async def is_owner(self, emote, user_id, *, force=False):
		"""return whether the user has permissions to modify this emote
		if force is True, return True as long as they are a moderator
		"""

		if user_id is None:
			return True

		if not emote:  # you can't own an emote that doesn't exist
			raise errors.EmoteNotFoundError(emote.name)

		return (force and await self.is_moderator(user_id)) or emote.author == user_id

	async def owner_check(self, emote, user_id, *, force=False):
		"""like is_owner but fails with an exception if the user is not authorized.
		this is to reduce duplicated exception raising code."""
		if not await self.is_owner(emote, user_id, force=force):
			raise errors.PermissionDeniedError(emote.name)

	## Actions

	async def create_emote(self, name, author_id, animated, image_data: bytes):
		await self.ensure_emote_does_not_exist(name)

		guild_id = await self.free_guild(animated)
		image = image_utils.image_to_base64_url(image_data)

		emote_data = await self.bot.http.create_custom_emoji(guild_id=guild_id, name=name, image=image)
		return DatabaseEmote(await self.bot.pool.fetchrow(
			self.queries.create_emote(), name, int(emote_data['id']), author_id, animated, guild_id))

	async def remove_emote(self, emote, user_id, *, force=False):
		"""Remove an emote given by name or DatabaseEmote object.
		-	user_id: the user trying to remove this emote,
			or None if their ownership should not
			be verified
		-	force: whether to remove the emote regardless of ownership status,
			as long as the user is a moderator

		returns the emote that was deleted
		"""
		if isinstance(emote, str):
			emote = await self.get_emote(name=emote)

		await self.owner_check(emote, user_id, force=force)

		try:
			await self.bot.http.delete_custom_emoji(emote.guild, emote.id)
		except discord.NotFound:
			# sometimes the database and the backend get out of sync
			# but we don't really care if there's an entry in the database and not the backend
			logger.warning(f'emote {emote.name} found in the database but not the backend! removing anyway.')

		tag = await self.bot.pool.execute(self.queries.remove_emote(), emote.id)
		if tag != 'DELETE 1':
			raise AssertionError
		return emote

	async def rename_emote(self, old_name, new_name, user_id):
		"""rename an emote from old_name to new_name. user_id must be authorized."""

		# don't fail if new_name is a different capitalization of old_name
		if old_name.lower() != new_name.lower():
			await self.ensure_emote_does_not_exist(new_name)

		emote = await self.get_emote(old_name)
		await self.owner_check(emote, user_id)

		await self.bot.http.edit_custom_emoji(emote.guild, emote.id, name=new_name)
		return DatabaseEmote(await self.bot.pool.fetchrow(self.queries.rename_emote(), emote.id, new_name))

	async def set_emote_creation(self, name, time: datetime):
		"""Set the creation time of an emote."""
		tag = await self.bot.pool.execute(self.queries.set_emote_creation(), name, time)
		if tag == 'UPDATE 0':
			raise errors.EmoteNotFoundError(name)

	async def set_emote_description(self, name, description=None, user_id=None):
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
			return DatabaseEmote(await self.bot.pool.fetchrow(
				self.queries.set_emote_description(), emote.id, description))
		except asyncpg.StringDataRightTruncationError as exception:
			# dumb way to do it but it's the only way i've got
			limit = int(re.search(r'character varying\((\d+)\)', exception.message)[1])
			raise errors.EmoteDescriptionTooLongError(emote.name, len(description), limit)

	async def set_emote_preservation(self, name, should_preserve: bool):
		"""change the preservation status of an emote.
		if an emote is preserved, it should not be decayed due to lack of use
		"""
		emote = await self.bot.pool.fetchrow(self.queries.set_emote_preservation(), name, should_preserve)

		# why are we doing this "if not emote" checking, when we could just call get_emote
		# before update?
		# because that would constitute an extra database query which we don't need
		if not emote:
			raise errors.EmoteNotFoundError(name)
		else:
			return DatabaseEmote(emote)

	async def toggle_emote_nsfw(self, emote: DatabaseEmote, *, by_mod=False):
		new_state = not emote.is_nsfw
		return await self.set_emote_nsfw(emote, new_state, by_mod=by_mod)

	async def set_emote_nsfw(self, emote: DatabaseEmote, new_state: bool, *, by_mod=False):
		new_status = self.new_nsfw_status(emote, new_state, by_mod=by_mod)

		return DatabaseEmote(await self.bot.pool.fetchrow(self.queries.set_emote_nsfw(), emote.id, new_status))

	@staticmethod
	def new_nsfw_status(emote, desired_status: bool, *, by_mod=False):
		if by_mod:
			# mods can do anything
			return 'MOD_NSFW' if desired_status else 'SFW'
		elif desired_status:
			return 'SELF_NSFW'

		# not by mod and SFW
		if emote.nsfw == 'MOD_NSFW':
			raise errors.PermissionDeniedError(
				_('You may not set this emote as SFW because it was set NSFW by an emote moderator.'))
		if emote.nsfw == 'SELF_NSFW':
			return 'SFW'

	async def delete_user_account(self, user_id):
		await self.delete_all_user_emotes(user_id)
		await self.delete_all_user_state(user_id)

	async def delete_all_user_emotes(self, user_id):
		async for emote in self.all_emotes(user_id):
			with contextlib.suppress(errors.EmoteError):
				# since we're only listing emotes by user_id,
				# we don't need to perform another ownership check
				# TODO use DELETE FROM
				await self.remove_emote(emote, user_id=None)

	async def log_emote_use(self, emote_id):
		await self.bot.pool.execute(self.queries.log_emote_use(), emote_id)

	async def decay(self):
		async for emote in self.decayable_emotes():
			logger.debug('decaying %s', emote.name)
			removal_messages = await self.logger.on_emote_decay(emote)
			try:
				await self.remove_emote(emote, user_id=None)
			except (errors.ConnoisseurError, errors.DiscordError) as ex:
				logger.error('decaying %s failed due to %s', emote.name, ex)
				await asyncio.gather(*map(operator.methodcaller('delete'), removal_messages), return_exceptions=True)

	def add_reply_message(self, invoking_message, reply_type: MessageReplyType, reply_message):
		"""add a record to indicate that the message with ID invoking_message is a reply_type message and that
		the bot replied with message ID reply_message
		"""
		return self.bot.pool.execute(
			self.queries.add_reply_message(), invoking_message, reply_type.value, reply_message)

	def delete_reply_by_invoking_message(self, invoking_message):
		"""remove and return one reply message ID for the given invoking message ID
		return None if no reply message was found.
		"""
		return self.bot.pool.fetchval(self.queries.delete_reply_by_invoking_message(), invoking_message)

	def delete_reply_by_reply_message(self, reply_message):
		"""remove one reply message entry for the given reply message ID"""
		return self.bot.pool.execute(self.queries.delete_reply_by_reply_message(), reply_message)

	## User / Guild Options

	async def delete_all_user_state(self, user_id):
		await self.bot.pool.execute('DELETE FROM user_opt WHERE id = $1', user_id)

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

	def _toggle_state(self, table_name, id, default):
		"""toggle the state for a user or guild. If there's no entry already, new state = default."""
		# TODO consider using one table, with an attribute for whether the state applies to a guild or a user
		return self.bot.pool.fetchval(self.queries.toggle_state(table_name), id, default)

	def toggle_guild_state(self, guild_id):
		"""Togle whether this guild is opt out.
		If this guild is opt in, the emote auto response will be disabled
		except for users that have opted in to it using `toggle_user_state`.
		Otherwise, the response will be on for all users except those that have opted out.
		"""
		return self._toggle_state('guild_opt', guild_id, False)

	def _get_state(self, table_name, id):
		return self.bot.pool.fetchval(self.queries.get_individual_state(table_name), id)

	def get_user_state(self, user_id):
		"""return this user's global preference for the emote auto response"""
		return self._get_state('user_opt', user_id)

	def get_guild_state(self, guild_id):
		"""return whether this guild is opt in"""
		return self._get_state('guild_opt', guild_id)

	def get_state(self, guild_id, user_id):
		"""return whether emote auto replies should be sent for the given user in the given guild"""
		# TODO investigate whether this obviates get_guild_state and get_user_state
		return self.bot.pool.fetchval(self.queries.get_state(), guild_id, user_id)

	## Blacklists

	def get_user_blacklist(self, user_id):
		"""return a reason for the user's blacklist, or None if not blacklisted"""
		return self.bot.pool.fetchval(self.queries.get_blacklist('user_opt'), user_id)

	async def set_user_blacklist(self, user_id, reason=None):
		"""make user_id blacklisted
		setting reason to None removes the user's blacklist
		"""
		await self.bot.pool.execute(self.queries.set_blacklist('user_opt'), user_id, reason)

	async def get_guild_blacklist(self, guild_id):
		return await self.bot.pool.fetchval(self.queries.get_blacklist('guild_opt'), guild_id)

	async def set_guild_blacklist(self, guild_id, reason=None):
		await self.bot.pool.execute(self.queries.set_blacklist('guild_opt'), guild_id, reason)

def setup(bot):
	bot.add_cog(Database(bot))
