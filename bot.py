#!/usr/bin/env python3
# encoding: utf-8

import logging
import traceback

from discord.ext import commands

from cogs.emoji import BackendContext
import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')
logger.setLevel(logging.DEBUG)


class EmojiConnoisseur(commands.Bot):
	cogs_path = 'cogs'

	def __init__(self, *args, **kwargs):
		self.config = db.CONFIG
		self.db = db.DB
		super().__init__(
			command_prefix=commands.when_mentioned_or('ec/'),
			description=self.config['description'],
			*args, **kwargs)

	async def on_ready(self):
		separator = '━' * 44
		logger.info(separator)
		logger.info('Logged in as: %s' % self.user)
		logger.info('ID: %s' % self.user.id)
		logger.info(separator)

	def should_reply(self, message):
		"""return whether the bot should reply to a given message"""
		# don't reply to bots, unless we're in dev mode
		# never reply to ourself
		return not (
			message.author == self.user
			or (message.author.bot and self.config['release'] != 'development')
			or not message.content)

	async def on_message(self, message):
		if not self.should_reply(message):
			return
		# inject the permissions checks
		await self.invoke(await self.get_context(message, cls=BackendContext))

	async def is_owner(self, user):
		if self.owner_id is None:
			app = await self.application_info()
			self.owner_id = app.owner.id

		return user.id == self.owner_id or str(user.id) in self.config['extra_owners']

	# https://github.com/Rapptz/RoboDanny/blob/ca75fae7de132e55270e53d89bc19dd2958c2ae0/bot.py#L77-L85
	async def on_command_error(self, context, error):
		if isinstance(error, commands.NoPrivateMessage):
			await context.author.send('This command cannot be used in private messages.')
		elif isinstance(error, commands.DisabledCommand):
			await context.author.send('Sorry. This command is disabled and cannot be used.')
		elif isinstance(error, commands.UserInputError):
			await context.send(error)
		elif isinstance(error, commands.NotOwner):
			logger.error('%s tried to run %s but is not the owner' % (context.author, context.command.name))
		elif isinstance(error, commands.CommandInvokeError):
			logger.error('In %s:' % context.command.qualified_name)
			logger.error(''.join(traceback.format_tb(error.original.__traceback__)))
			logger.error('{0.__class__.__name__}: {0}'.format(error.original))

	def run(self, *args, **kwargs):
		for extension in (
				'cogs.utils',  # load first, since other cogs depend on it
				'cogs.emoji',
				'cogs.meta',
				'jishaku',
				'cogs.stats',
				'cogs.external.misc'):
			try:
				self.load_extension(extension)
			except:  # pylint: disable=bare-except
				logger.error('Failed to load ' + extension)
				logger.error(traceback.format_exc())
			else:
				logger.info('Successfully loaded ' + extension)

		super().run(self.config['tokens']['discord'], *args, **kwargs)


# defined in a function so it can be run from a REPL if need be
def run():
	EmojiConnoisseur().run()


if __name__ == '__main__':
	run()
