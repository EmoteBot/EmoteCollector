#!/usr/bin/env python3.6
# encoding: utf-8

import logging
import re
import traceback

import discord
from discord.ext import commands

from utils import CustomContext, load_json_compat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')
logger.setLevel(logging.DEBUG)


class EmojiConnoisseur(commands.AutoShardedBot):
	def __init__(self, *args, **kwargs):
		with open('data/config.py') as conf:
			self.config = load_json_compat(conf.read())
			# make lookup fast
			self.config['extra_owners'] = frozenset(self.config['extra_owners'])

		super().__init__(
			#command_prefix=commands.when_mentioned_or(self.config['prefix']),
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

	async def on_message(self, message):
		if not self.should_reply(message):
			return
		# inject our context
		await self.invoke(await self.get_context(message, cls=CustomContext))

	def should_reply(self, message):
		"""return whether the bot should reply to a given message"""
		# don't reply to bots, unless we're in dev mode
		# never reply to ourself
		return not (
			message.author == self.user
			or (message.author.bot and self._should_reply_to_bot(message))
			or not message.content)

	def _should_reply_to_bot(self, message):
		should_reply = not self.config['ignore_bots'].get('default')
		overrides = self.config['ignore_bots'].get('overrides', {})

		def check_override(obj, attr):
			print(obj, attr)
			location = getattr(obj, attr)
			print(location and getattr(location, 'id') in overrides.get(attr, frozenset()))
			return location and getattr(location, 'id') in overrides.get(attr, frozenset())

		if check_override(message, 'guild') or check_override(message, 'channel'):
			should_reply = not should_reply

		return should_reply

	async def is_owner(self, user):
		if self.owner_id is None:
			app = await self.application_info()
			self.owner_id = app.owner.id

		return user.id == self.owner_id or user.id in self.config['extra_owners']

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
			logger.error('In %s:', context.command.qualified_name)
			logger.error(''.join(traceback.format_tb(error.original.__traceback__)))
			# pylint: disable=logging-format-interpolation
			logger.error('{0.__class__.__name__}: {0}'.format(error.original))

	def run(self, *args, **kwargs):
		for extension in (
				'cogs.utils',  # load first, since other cogs depend on it
				'cogs.logging',
				'cogs.db',
				'cogs.emoji',
				'cogs.meta',
				'jishaku',
				'cogs.stats',
				'ben_cogs.misc',
				'cogs.meme',
				'ben_cogs.debug'):
			try:
				self.load_extension(extension)
			except:  # pylint: disable=bare-except
				logger.error('Failed to load %s', extension)
				logger.error(traceback.format_exc())
			else:
				logger.info('Successfully loaded %s', extension)

		super().run(self.config['tokens']['discord'], *args, **kwargs)


# defined in a function so it can be run from a REPL if need be
def run():
	EmojiConnoisseur().run()


if __name__ == '__main__':
	run()
