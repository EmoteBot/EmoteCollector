#!/usr/bin/env python3
# encoding: utf-8

import logging
import traceback

from discord.ext import commands

from cogs.emoji import EmoteContext
import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')
logger.setLevel(logging.DEBUG)


class EmojiConnoisseur(commands.Bot):
	cogs_path = 'cogs'

	def __init__(self, *args, **kwargs):
		self.config = db.CONFIG
		self.db = db.DB
		super().__init__(command_prefix=commands.when_mentioned_or('ec/'), *args, **kwargs)

	async def on_ready(self):
		# idk why but loading this cog before ready doesn't work
		self.load_extension('jishaku')
		separator = '━' * 44
		logger.info(separator)
		logger.info('Logged in as: %s' % self.user)
		logger.info('ID: %s' % self.user.id)
		logger.info(separator)

	async def on_message(self, message):
		# inject the permissions checks
		await self.invoke(await self.get_context(message, cls=EmoteContext))

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
		elif isinstance(error, commands.CommandInvokeError):
			logger.error('In %s:' % context.command.qualified_name)
			logger.error(''.join(traceback.format_tb(error.original.__traceback__)))
			logger.error('{0.__class__.__name__}: {0}'.format(error.original))

	def run(self, *args, **kwargs):
		for extension in ('emoji', 'meta', 'external.stats', 'external.misc'):
			try:
				self.load_extension(self.cogs_path + '.' + extension)
			except:
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
