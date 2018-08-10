#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import contextlib
import logging
import re
import traceback

import aiofiles
import asyncpg
import discord
from discord.ext import commands
try:
	import uvloop
except ImportError:
	pass  # Windows
else:
	asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

import utils


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')

class EmojiConnoisseur(commands.AutoShardedBot):
	def __init__(self, *args, **kwargs):
		with open('data/config.py') as conf:
			self.config = utils.load_json_compat(conf.read())

			self.owners = set(self.config['extra_owners'])
			if self.config.get('primary_owner'):
				self.owners.add(self.config['primary_owner'])

		self.db_ready = asyncio.Event()

		super().__init__(
			command_prefix=self.get_prefix_,
			description=self.config['description'],
			activity=discord.Game(name=self.config['prefix'] + 'help'),  # "Playing ec/help"
			*args, **kwargs)

	async def get_prefix_(self, bot, message):
		prefix = self.config['prefix']
		match = re.search(fr'^{prefix}', message.content, re.IGNORECASE)
		# if there's no match then we want to pass no prefixes into when_mentioned_or

		if match is None:
			return commands.when_mentioned(bot, message)
		else:
			return commands.when_mentioned_or(match.group(0))(bot, message)

	async def on_ready(self):
		separator = '━' * 44
		logger.info(separator)
		logger.info('Logged in as: %s', self.user)
		logger.info('ID: %s', self.user.id)
		logger.info(separator)

	async def get_context(self, message, **kwargs):
		return await super().get_context(message, cls=utils.context.CustomContext, **kwargs)

	async def on_message(self, message):
		if self.should_reply(message):
			await self.process_commands(message)

	def should_reply(self, message):
		"""return whether the bot should reply to a given message"""
		return not (
			message.author == self.user
			or (message.author.bot and not self._should_reply_to_bot(message))
			or not message.content)

	def _should_reply_to_bot(self, message):
		should_reply = not self.config['ignore_bots'].get('default')
		overrides = self.config['ignore_bots']['overrides']

		def check_override(location, overrides_key):
			return location and location.id in overrides[overrides_key]

		if check_override(message.guild, 'guilds') or check_override(message.channel, 'channels'):
			should_reply = not should_reply

		return should_reply

	async def is_owner(self, user):
		if self.owner_id is None:
			app = await self.application_info()
			self.owner_id = app.owner.id

		return user.id == self.owner_id or user.id in self.owners

	# https://github.com/Rapptz/RoboDanny/blob/ca75fae7de132e55270e53d89bc19dd2958c2ae0/bot.py#L77-L85
	async def on_command_error(self, context, error):
		if isinstance(error, commands.NoPrivateMessage):
			await context.author.send('This command cannot be used in private messages.')
		elif isinstance(error, commands.DisabledCommand):
			message = 'Sorry. This command is disabled and cannot be used.'
			try:
				await context.author.send(message)
			except discord.Forbidden:
				await context.send(message)
		elif isinstance(error, commands.UserInputError):
			await context.send(error)
		elif isinstance(error, commands.NotOwner):
			logger.error('%s tried to run %s but is not the owner', context.author, context.command.name)
		elif isinstance(error, commands.CommandInvokeError):
			await context.send('An internal error occured while trying to run that command.')

			logger.error('"%s" caused an exception', context.message.content)
			logger.error(''.join(traceback.format_tb(error.original.__traceback__)))
			# pylint: disable=logging-format-interpolation
			logger.error('{0.__class__.__name__}: {0}'.format(error.original))

	async def logout(self):
		await self.pool.close()
		await super().logout()

	async def start(self):
		await self._init_db()
		self._load_extensions()

		await super().start(self.config['tokens'].pop('discord'))

	async def _init_db(self):
		credentials = self.config.pop('database')
		pool = await asyncpg.create_pool(**credentials)

		async with aiofiles.open('data/schema.sql') as f:
			await pool.execute(await f.read())

		self.pool = pool
		self.db_ready.set()

	def _load_extensions(self):
		for extension in (
				'extensions.logging',
				'extensions.db',
				'extensions.emote',
				'extensions.api',
				'extensions.meta',
				'jishaku',
				'extensions.stats',
				'ben_cogs.misc',
				'extensions.meme',
				'ben_cogs.debug',
		):
			self.load_extension(extension)
			logger.info('Successfully loaded %s', extension)

# defined in a function so it can be run from a REPL if need be
def run():
	loop = asyncio.get_event_loop()
	bot = EmojiConnoisseur(loop=loop)

	with contextlib.closing(loop):
		try:
			loop.run_until_complete(bot.start())
		finally:
			loop.run_until_complete(bot.logout())

if __name__ == '__main__':
	run()
