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
import inspect
import itertools
import json
import logging
import traceback
from pathlib import Path

import asyncpg
import discord
import jinja2
from bot_bin.bot import Bot
from braceexpand import braceexpand
from discord.ext import commands
try:
	import uvloop
except ImportError:
	pass  # Windows
else:
	asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# set BASE_DIR before importing utils because utils.i18n depends on it
BASE_DIR = Path(__file__).parent

from . import utils
from . import extensions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')

class EmoteCollector(Bot):
	def __init__(self, **kwargs):
		super().__init__(setup_db=True, **kwargs)
		self.jinja_env = jinja2.Environment(
			loader=jinja2.FileSystemLoader(str(BASE_DIR / 'sql')),
			line_statement_prefix='-- :')

	def process_config(self):
		super().process_config()
		self.config['backend_user_accounts'] = set(self.config['backend_user_accounts'])
		with contextlib.suppress(KeyError):
			self.config['copyright_license_file'] = BASE_DIR / self.config['copyright_license_file']
		utils.SUCCESS_EMOJIS = self.config.get('success_or_failure_emojis', ('❌', '✅'))

	### Events

	async def on_message(self, message):
		if self.should_reply(message):
			await self.set_locale(message)
			await self.process_commands(message)

	async def set_locale(self, message):
		locale = await self.cogs['Locales'].locale(message)
		utils.i18n.current_locale.set(locale)

	# https://github.com/Rapptz/RoboDanny/blob/ca75fae7de132e55270e53d89bc19dd2958c2ae0/bot.py#L77-L85
	async def on_command_error(self, context, error):
		if isinstance(error, commands.NoPrivateMessage):
			await context.author.send(_('This command cannot be used in private messages.'))
		elif isinstance(error, commands.DisabledCommand):
			await context.send(_('Sorry. This command is disabled and cannot be used.'))
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

	# https://github.com/Rapptz/discord.py/blob/814b03f5a8a6faa33d80495691f1e1cbdce40ce2/discord/ext/commands/core.py#L1338-L1346
	def has_permissions(self, message, **perms):
		guild = message.guild
		me = guild.me if guild is not None else self.user
		permissions = message.channel.permissions_for(me)

		for perm, value in perms.items():
			if getattr(permissions, perm, None) != value:
				return False

		return True

	def queries(self, template_name):
		return self.jinja_env.get_template(str(template_name)).module

	### Init / Shutdown

	startup_extensions = list(braceexpand("""{
		emote_collector.extensions.{
			locale,
			file_upload_hook,
			logging,
			db,
			emote,
			api,
			gimme,
			meta,
			stats,
			meme,
			bingo.{
				db,
				commands}},
		jishaku,
		bot_bin.{
			misc,
			debug,
			sql}}
	""".replace('\t', '').replace('\n', '')))

	def load_extensions(self):
		utils.i18n.set_default_locale()
		super().load_extensions()
