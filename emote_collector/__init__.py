#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import contextlib
import inspect
import itertools
import logging
import os.path
import re
import traceback
import uuid

import asyncpg
import discord
from discord.ext import commands
try:
	import uvloop
except ImportError:
	pass  # Windows
else:
	asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# set BASE_DIR before importing utils because utils.i18n depends on it
BASE_DIR = os.path.dirname(__file__)

from . import utils
from . import extensions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')

class EmoteCollector(commands.AutoShardedBot):
	def __init__(self, *args, **kwargs):
		self.config = kwargs.pop('config')
		self.process_config()
		self._fallback_prefix = str(uuid.uuid4())

		super().__init__(
			command_prefix=self.get_prefix_,
			description=self.config.get('description'),
			activity=self.activity,
			*args, **kwargs)

	def process_config(self):
		self.owners = set(self.config.get('extra_owners', ()))
		if self.config.get('primary_owner'):
			self.owners.add(self.config['primary_owner'])
		self.config['backend_user_accounts'] = set(self.config['backend_user_accounts'])

		with contextlib.suppress(KeyError):
			self.config['copyright_license_file'] = os.path.join(BASE_DIR, self.config['copyright_license_file'])
		self._setup_success_emojis()

	def _setup_success_emojis(self):
		utils.SUCCESS_EMOJIS = utils.misc.SUCCESS_EMOJIS = (
			self.config.get('success_or_failure_emojis', ('❌', '✅')))

	@property
	def prefix_re(self):
		prefix = self.config['prefix']
		if isinstance(prefix, str):
			prefixes = [prefix]
		else:
			prefixes = prefix

		prefixes = list(prefixes)  # ensure it's not a tuple
		if self.is_ready():
			prefixes.extend([f'<@{self.user.id}>', f'<@!{self.user.id}>'])

		prefixes = '|'.join(map(re.escape, prefixes))
		prefixes = f'(?:{prefixes})'

		return re.compile(f'^\N{zero width space}?{prefixes}\\s*', re.IGNORECASE)

	@property
	def activity(self):
		prefix = self.config['prefix']
		if isinstance(prefix, str):
			prefix = (prefix,)
		return discord.Game(name=prefix[0]+'help')

	def get_prefix_(self, bot, message):
		match = self.prefix_re.search(message.content)

		if match is None:
			# Callable prefixes must always return at least one prefix,
			# but no prefix was found in the message,
			# so we still have to return *something*.
			# Use a UUID because it's practically guaranteed not to be in the message.
			return self._fallback_prefix
		else:
			return match[0]

	### Events

	async def on_ready(self):
		separator = '━' * 44
		logger.info(separator)
		logger.info('Logged in as: %s', self.user)
		logger.info('ID: %s', self.user.id)
		logger.info(separator)

	async def on_message(self, message):
		if self.should_reply(message):
			await self.set_locale(message)
			await self.process_commands(message)

	async def set_locale(self, message):
		locale = await self.get_cog('Locales').locale(message)
		utils.i18n.current_locale.set(locale)

	async def process_commands(self, message):
		# overridden because the default process_commands ignores bots now
		context = await self.get_context(message)
		await self.invoke(context)

	# https://github.com/Rapptz/RoboDanny/blob/ca75fae7de132e55270e53d89bc19dd2958c2ae0/bot.py#L77-L85
	async def on_command_error(self, context, error):
		if isinstance(error, commands.NoPrivateMessage):
			await context.author.send(_('This command cannot be used in private messages.'))
		elif isinstance(error, commands.DisabledCommand):
			message = _('Sorry. This command is disabled and cannot be used.')
			try:
				await context.author.send(message)
			except discord.Forbidden:
				await context.send(message)
		elif isinstance(error, commands.NotOwner):
			logger.error('%s tried to run %s but is not the owner', context.author, context.command.name)
			with contextlib.suppress(discord.HTTPException):
				await context.try_add_reaction(utils.SUCCESS_EMOJIS[False])
		elif isinstance(error, (commands.UserInputError, commands.CheckFailure)):
			await context.send(error)
		elif (
			isinstance(error, commands.CommandInvokeError)
			# abort if it's overridden
			and
				getattr(
					type(context.cog),
					'cog_command_error',
					# treat ones with no cog (e.g. eval'd ones) as being in a cog that did not override
					commands.Cog.cog_command_error)
				is commands.Cog.cog_command_error
		):
			if not isinstance(error.original, discord.HTTPException):
				logger.error('"%s" caused an exception', context.message.content)
				logger.error(''.join(traceback.format_tb(error.original.__traceback__)))
				# pylint: disable=logging-format-interpolation
				logger.error('{0.__class__.__name__}: {0}'.format(error.original))

				await context.send(_('An internal error occurred while trying to run that command.'))
			elif isinstance(error.original, discord.Forbidden):
				await context.send(_("I'm missing permissions to perform that action."))

	### Utility functions

	async def get_context(self, message, cls=None):
		return await super().get_context(message, cls=cls or utils.context.CustomContext)

	def should_reply(self, message):
		"""return whether the bot should reply to a given message"""
		return not (
			message.author == self.user
			or (message.author.bot and not self._should_reply_to_bot(message))
			or not message.content)

	async def is_owner(self, user):
		return await super().is_owner(user) or user.id in self.owners

	# https://github.com/Rapptz/discord.py/blob/814b03f5a8a6faa33d80495691f1e1cbdce40ce2/discord/ext/commands/core.py#L1338-L1346
	def has_permissions(self, message, **perms):
		guild = message.guild
		me = guild.me if guild is not None else self.user
		permissions = message.channel.permissions_for(me)

		for perm, value in perms.items():
			if getattr(permissions, perm, None) != value:
				return False

		return True

	def _should_reply_to_bot(self, message):
		should_reply = not self.config['ignore_bots'].get('default')
		overrides = self.config['ignore_bots']['overrides']

		def check_override(location, overrides_key):
			return location and location.id in overrides[overrides_key]

		if check_override(message.guild, 'guilds') or check_override(message.channel, 'channels'):
			should_reply = not should_reply

		return should_reply

	### Init / Shutdown

	async def start(self, token=None, **kwargs):
		await self.init_db()
		self._load_extensions()

		await super().start(self.config['tokens'].pop('discord'), **kwargs)

	async def close(self):
		with contextlib.suppress(AttributeError):
			await self.pool.close()
		await super().close()

	async def init_db(self):
		credentials = self.config['database']
		self.pool = await asyncpg.create_pool(**credentials)

	def _load_extensions(self):
		utils.i18n.set_default_locale()
		for extension in (
			'emote_collector.extensions.locale',
			'emote_collector.extensions.file_upload_hook',
			'emote_collector.extensions.logging',
			'emote_collector.extensions.db',
			'emote_collector.extensions.emote',
			'emote_collector.extensions.api',
			'emote_collector.extensions.gimme',
			'emote_collector.extensions.meta',
			'emote_collector.extensions.stats',
			'emote_collector.extensions.meme',
			'jishaku',
			'ben_cogs.misc',
			'ben_cogs.debug',
			'ben_cogs.sql',
		):
			self.load_extension(extension)
			logger.info('Successfully loaded %s', extension)
