#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import getopt
import inspect
import shlex
import os
import pkg_resources
import textwrap
import weakref

import psutil

import discord
from discord.ext import commands

from ..utils import asyncexecutor
from ..utils.paginator import HelpPaginator, CannotPaginate

class Meta(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

		# setting a Command as an attribute of a cog causes it to be added to the bot
		# prevent this by wrapping it in a tuple
		self.old_help = (self.bot.remove_command('help'),)

		self.paginators = weakref.WeakSet()
		self.process = psutil.Process()

	def cog_unload(self):
		async def stop_all():
			for paginator in self.paginators:
				await paginator.stop(delete=False)

		self.bot.loop.create_task(stop_all())

	@commands.command(name='delete-my-account')
	async def delete_my_account(self, context):
		"""Permanently deletes all information I have on you.
		This includes:
			• Any emotes you have created
			• Any settings you have made
			• Your API token, if you have one

		This does *not* include which emotes you have used, since I don't log *who* uses each emote,
		only *when* each emote is used.

		This command may take a while to run, especially if you've made a lot of emotes.
		"""

		confirmation_phrase = _('Yes, delete my account.')
		prompt = _(
			'Are you sure you want to delete your account? '
			'To confirm, please say “{confirmation_phrase}” exactly.'
		).format(**locals())

		if not await self.confirm(context, prompt, confirmation_phrase):
			return

		status_message = await context.send(_('Deleting your account…'))

		async with context.typing():
			for cog_name in 'Database', 'Locales', 'API':
				await self.bot.get_cog(cog_name).delete_user_account(user_id)

		await status_message.delete()
		await context.send(_("{context.author.mention} I've deleted your account successfully.").format(**locals()))

	async def confirm(self, context, prompt, required_phrase, *, timeout=30):
		await context.send(prompt)

		def check(message):
			return (
				message.author == context.author
				and message.channel == context.channel
				and message.content == required_phrase)

		try:
			await self.bot.wait_for('message', check=check, timeout=timeout)
		except asyncio.TimeoutError:
			await context.send(_('Confirmation phrase not received in time. Please try again.'))
			return False
		else:
			return True

	@commands.command()
	async def help(self, context, *, args: str=None):
		if args is None:
			paginator = await HelpPaginator.from_bot(context)
			self.paginators.add(paginator)
			return await paginator.begin()

		args = shlex.split(args)
		try:
			opts, args = getopt.gnu_getopt(args, '', ['embed', 'no-embed'])
		except getopt.GetoptError:
			opts = []

		# since opts is a list of two-tuples, we can't use frozenset on it directly
		# so we have to call dict first
		opts = frozenset(dict(opts))
		if len(opts) == 2:
			raise commands.BadArgument('Only one of --embed, --no-embed is expected.')

		embed = True if '--embed' in opts else False if '--no-embed' in opts else True

		if not args:
			if embed:
				paginator = await HelpPaginator.from_bot(context)
				self.paginators.add(paginator)
				return await paginator.begin()
			return await context.send_help()

		# derived from R.Danny's help command
		# https://github.com/Rapptz/RoboDanny/blob/8919ec0a455f957848ef77b479fe3494e76f0aa7/cogs/meta.py
		# MIT Licensed, Copyright © 2015 Rapptz

		# it came from getopt so it's still a bunch of args
		command = ' '.join(args)

		entity = self.bot.get_cog(command) or self.bot.get_command(command)

		if entity is self.help:
			return await context.send(_(textwrap.dedent("""
				```
				{context.prefix}help [commands...]

				Shows help about a command, category, or the bot.

				Optional arguments:
					--embed    display output with an embed
					--no-embed display output without an embed
				```""")).format(**locals()))
		elif not embed:
			return await context.send_help(command)

		if entity is None:
			command_name = command.replace('@', '@\N{zero width non-joiner}')
			return await context.send(_('Command or category "{command_name}" not found.').format(**locals()))
		elif isinstance(entity, commands.Command):
			paginator = await HelpPaginator.from_command(context, entity)
		else:
			paginator = await HelpPaginator.from_cog(context, entity)

		self.paginators.add(paginator)
		await paginator.begin()

	@help.error
	async def help_error(self, context, error):
		if isinstance(error, CannotPaginate):
			await context.send(error)

	@commands.command()
	async def about(self, context):
		"""Tells you information about the bot itself."""
		# this command is based off of code provided by Rapptz under the MIT license
		# https://github.com/Rapptz/RoboDanny/blob/f6638d520ea0f559cb2ae28b862c733e1f165970/cogs/stats.py
		# Copyright © 2015 Rapptz

		embed = discord.Embed(description=self.bot.config['description'])

		embed.add_field(name='Latest changes', value=await self._latest_changes(), inline=False)

		embed.title = 'Official Bot Support Invite'
		invite_code = self.bot.config['support_server'].get('invite_code')
		if invite_code:
			embed.url = 'https://discord.gg/' + invite_code

		owner = self.bot.get_user(self.bot.config.get('primary_owner', self.bot.owner_id))
		embed.set_author(name=str(owner), icon_url=owner.avatar_url)

		embed.add_field(name='Servers', value=await self.bot.get_cog('Stats').guild_count())

		debug_cog = self.bot.get_cog('BenCogsDebug')
		cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
		embed.add_field(name='Process', value=f'{debug_cog.memory_usage()}\n{cpu_usage:.2f}% CPU')

		embed.add_field(name='Uptime', value=self.bot.get_cog('BenCogsMisc').uptime(brief=True))
		embed.set_footer(text='Made with discord.py', icon_url='https://i.imgur.com/5BFecvA.png')

		await context.send(embed=embed)

	@asyncexecutor()
	def _latest_changes(self):
		cmd = fr'git log -n 3 -s --format="[{{}}]({self.bot.config["repo"]}/commit/%H) %s (%cr)"'
		if os.name == 'posix':
			cmd = cmd.format(r'\`%h\`')
		else:
			cmd = cmd.format(r'`%h`')

		try:
			return os.popen(cmd).read().strip()
		except OSError:
			return _('Could not fetch changes due to memory error. Sorry.')

	@commands.command()
	async def support(self, context):
		"""Directs you to the support server."""
		try:
			await context.author.send('https://discord.gg/' + self.bot.config['support_server']['invite_code'])
		except discord.HTTPException:
			await context.try_add_reaction(utils.SUCCESS_EMOJIS[False])
			with contextlib.suppress(discord.HTTPException):
				await context.send(_('Unable to send invite in DMs. Please allow DMs from server members.'))
		else:
			await context.try_add_reaction('\N{open mailbox with raised flag}')

	@commands.command(aliases=['inv'])
	async def invite(self, context):
		"""Gives you a link to add me to your server."""
		# these are the same as the attributes of discord.Permissions
		permission_names = (
			'read_messages',
			'send_messages',
			'read_message_history',
			'external_emojis',
			'add_reactions',
			'manage_messages',
			'embed_links')
		permissions = discord.Permissions()
		permissions.update(**dict.fromkeys(permission_names, True))
		await context.send('<%s>' % discord.utils.oauth_url(self.bot.config['client_id'], permissions))

	# heavily based on code provided by Rapptz, © 2015 Rapptz
	# https://github.com/Rapptz/RoboDanny/blob/8919ec0a455f957848ef77b479fe3494e76f0aa7/cogs/meta.py#L162-L190
	@commands.command()
	async def source(self, context, *, command: str = None):
		"""Displays my full source code or for a specific command.
		To display the source code of a subcommand you can separate it by
		periods, e.g. locale.set for the set subcommand of the locale command
		or by spaces.
		"""
		source_url = self.bot.config['repo']
		if command is None:
			return await context.send(source_url)

		obj = self.bot.get_command(command.replace('.', ' '))
		if obj is None:
			return await context.send('Could not find command.')

		# since we found the command we're looking for, presumably anyway, let's
		# try to access the code itself
		src = obj.callback
		lines, firstlineno = inspect.getsourcelines(src)
		module = inspect.getmodule(src).__name__
		if module.startswith(self.__module__.split('.')[0]):  # XXX dunno if this branch works
			# not a built-in command
			location = os.path.relpath(inspect.getfile(src)).replace('\\', '/')
			at = await self._current_revision()
		elif module.startswith('discord'):
			source_url = 'https://github.com/Rapptz/discord.py'
			at = self._discord_revision()
		else:
			if module.startswith('jishaku'):
				source_url = 'https://github.com/Gorialis/jishaku'
				at = self._pkg_version('jishaku')
			elif module.startswith('ben_cogs'):
				source_url = 'https://github.com/bmintz/cogs'
				at = self._ben_cogs_revision()

			location = module.replace('.', '/') + '.py'

		final_url = f'<{source_url}/blob/{at}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
		await context.send(final_url)

	@staticmethod
	@asyncexecutor()
	def _current_revision(*, default='master'):
		try:
			return os.popen('git rev-parse HEAD').read().strip()
		except OSError:
			return default

	@classmethod
	def _discord_revision(cls, *, default='rewrite'):
		ver = cls._pkg_version('discord', default=default)
		if ver == default:
			return default

		version, sep, commit = ver.rpartition('+g')
		return commit or default

	@classmethod
	def _ben_cogs_revision(cls, *, default='master'):
		ver = cls._pkg_version('ben_cogs', default=default)
		if ver == default:
			return default

		return 'v' + ver

	@staticmethod
	def _pkg_version(pkg, *, default='master'):
		try:
			return pkg_resources.get_distribution(pkg).version
		except pkg_resources.DistributionNotFound:
			return default

def setup(bot):
	bot.add_cog(Meta(bot))
	if not bot.config.get('repo'):
		bot.remove_command('source')
	if not bot.config['support_server'].get('invite_code'):
		bot.remove_command('support')
