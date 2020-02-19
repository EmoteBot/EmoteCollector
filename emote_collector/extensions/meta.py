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
import inspect
import itertools
import os
import pkg_resources

import discord
import humanize
import pygit2
import psutil
from discord.ext import commands

from ..utils import asyncexecutor
from ..utils.paginator import Pages, CannotPaginate

# Using code provided by Rapptz under the MIT License
# Copyright ©︎ 2015 Rapptz
# https://github.com/Rapptz/RoboDanny/blob/915c8721c899caadfc902e2b8557d3693f3fd866/cogs/meta.py

class HelpPaginator(Pages):
	def __init__(self, help_command, ctx, entries, *, per_page=4):
		super().__init__(ctx, entries=entries, per_page=per_page)
		self.reaction_emojis['\N{WHITE QUESTION MARK ORNAMENT}'] = self.show_bot_help
		self.total = len(entries)
		self.help_command = help_command
		self.prefix = help_command.clean_prefix
		self.is_bot = False

	def get_bot_page(self, page):
		cog_name, description, commands = self.entries[page - 1]
		self.title = _('{cog_name} Commands').format(**locals())
		self.description = description
		return commands

	def prepare_embed(self, entries, page, *, first=False):
		self.embed.clear_fields()
		self.embed.description = self.description
		self.embed.title = self.title

		invite_code = self.bot.config['support_server'].get('invite_code')
		if self.is_bot and invite_code:
			invite = f'https://discord.gg/{invite_code}'
			value = _('For more help, join the official bot support server: {invite}').format(**locals())
			self.embed.add_field(name=_('Support'), value=value, inline=False)

		self.embed.set_footer(
			text=_('Use "{self.prefix}help command" for more info on a command.').format(**locals()))

		for entry in entries:
			signature = f'{entry.qualified_name} {entry.signature}'
			self.embed.add_field(name=signature, value=entry.short_doc or _('No help given'), inline=False)

		if self.maximum_pages:
			self.embed.set_footer(
				text=_('Page {page}⁄{self.maximum_pages} ({self.total} commands)').format(**locals()))

	async def show_help(self):
		"""shows this message"""

		self.embed.title = _('Paginator help')
		self.embed.description = _('Hello! Welcome to the help page.')

		messages = [f'{emoji} {func.__doc__}' for emoji, func in self.reaction_emojis.items()]
		self.embed.clear_fields()
		self.embed.add_field(name=_('What are these reactions for?'), value='\n'.join(messages), inline=False)

		self.embed.set_footer(
			text=_('We were on page {self.current_page} before this message.').format(**locals()))
		await self.message.edit(embed=self.embed)

		async def go_back_to_current_page():
			await asyncio.sleep(30.0)
			await self.show_current_page()

		self.bot.loop.create_task(go_back_to_current_page())

	async def show_bot_help(self):
		"""shows how to use the bot"""

		self.embed.title = _('Using the bot')
		self.embed.description = _('Hello! Welcome to the help page.')
		self.embed.clear_fields()

		self.embed.add_field(name=_('How do I use this bot?'), value=_('Reading the bot signature is pretty simple.'))

		argument = _('argument')

		entries = (
			(f'<{argument}>', _('This means the argument is __**required**__.')),
			(f'[{argument}]', _('This means the argument is __**optional**__.')),
			(f'[A|B]', _('This means the it can be __**either A or B**__.')),
			(
				f'[{argument}...]',
				_('This means you can have multiple arguments.\n'
				'Now that you know the basics, it should be noted that...\n'
				'__**You do not type in the brackets!**__')
			)
		)

		for name, value in entries:
			self.embed.add_field(name=name, value=value, inline=False)

		self.embed.set_footer(text=_('We were on page {self.current_page} before this message.').format(**locals()))
		await self.message.edit(embed=self.embed)

		async def go_back_to_current_page():
			await asyncio.sleep(30.0)
			await self.show_current_page()

		self.bot.loop.create_task(go_back_to_current_page())

class PaginatedHelpCommand(commands.HelpCommand):
	def __init__(self):
		super().__init__(command_attrs={
			'cooldown': commands.Cooldown(1, 3.0, commands.BucketType.member),
			'help': _('Shows help about the bot, a command, or a category')
		})

	async def on_help_command_error(self, ctx, error):
		if isinstance(error, commands.CommandInvokeError):
			await ctx.send(str(error.original))

	def get_command_signature(self, command):
		parent = command.full_parent_name
		if len(command.aliases) > 0:
			aliases = '|'.join(command.aliases)
			fmt = f'[{command.name}|{aliases}]'
			if parent:
				fmt = f'{parent} {fmt}'
			alias = fmt
		else:
			alias = command.name if not parent else f'{parent} {command.name}'
		return f'{alias} {command.signature}'

	async def send_bot_help(self, mapping):
		def key(c):
			# zero width space so that "No Category" gets sorted first
			return c.cog_name or '\N{zero width space}' + _('No Category')

		bot = self.context.bot
		entries = await self.filter_commands(bot.commands, sort=True, key=key)
		nested_pages = []
		per_page = 9
		total = 0

		for cog, commands in itertools.groupby(entries, key=key):
			commands = sorted(commands, key=lambda c: c.name)
			if len(commands) == 0:
				continue

			total += len(commands)
			actual_cog = bot.get_cog(cog)
			# get the description if it exists (and the cog is valid) or return Empty embed.
			description = (actual_cog and actual_cog.description) or discord.Embed.Empty
			nested_pages.extend((cog, description, commands[i:i + per_page]) for i in range(0, len(commands), per_page))

		# a value of 1 forces the pagination session
		pages = HelpPaginator(self, self.context, nested_pages, per_page=1)

		# swap the get_page implementation to work with our nested pages.
		pages.get_page = pages.get_bot_page
		pages.is_bot = True
		pages.total = total
		await pages.begin()

	async def send_cog_help(self, cog):
		entries = await self.filter_commands(cog.get_commands(), sort=True)
		pages = HelpPaginator(self, self.context, entries)
		cog_name = cog.qualified_name  # preserve i18n'd strings which use this var name
		pages.title = _('{cog_name} Commands').format(**locals())
		pages.description = cog.description

		await pages.begin()

	def common_command_formatting(self, page_or_embed, command):
		page_or_embed.title = self.get_command_signature(command)
		if command.description:
			page_or_embed.description = f'{command.description}\n\n{command.help}'
		else:
			page_or_embed.description = command.help or _('No help given.')

	async def send_command_help(self, command):
		# No pagination necessary for a single command.
		embed = discord.Embed()
		self.common_command_formatting(embed, command)
		await self.context.send(embed=embed)

	async def send_group_help(self, group):
		subcommands = group.commands
		if len(subcommands) == 0:
			return await self.send_command_help(group)

		entries = await self.filter_commands(subcommands, sort=True)
		pages = HelpPaginator(self, self.context, entries)
		self.common_command_formatting(pages, group)

		await pages.begin()

	def command_not_found(self, command_name):
		return _('Command or category "{command_name}" not found.').format(**locals())

	def subcommand_not_found(self, command, subcommand):
		if isinstance(command, commands.Group) and len(command.all_commands) > 0:
			return _('Command "{command.qualified_name}" has no subcommand named {subcommand}').format(**locals())
		return _('Command "{command.qualified_name}" has no subcommands.').format(**locals())

class Meta(commands.Cog):
	# TODO does this need to be configurable?
	INVITE_DURATION_SECONDS = 60 * 60 * 3
	MAX_INVITE_USES = 5

	def __init__(self, bot):
		self.bot = bot

		self.old_help = self.bot.help_command
		self.bot.help_command = PaginatedHelpCommand()
		self.bot.help_command.cog = self

		self.process = psutil.Process()

	def cog_unload(self):
		self.bot.help_command = self.old_help

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
			for cog_name in 'Database', 'Locales', 'API', 'BingoDatabase':
				await self.bot.cogs[cog_name].delete_user_account(context.author.id)

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
	async def about(self, context):
		"""Tells you information about the bot itself."""
		# this command is based off of code provided by Rapptz under the MIT license
		# https://github.com/Rapptz/RoboDanny/blob/f6638d520ea0f559cb2ae28b862c733e1f165970/cogs/stats.py
		# Copyright © 2015 Rapptz

		embed = discord.Embed(description=self.bot.config['description'])

		embed.add_field(name='Latest changes', value=await self._latest_changes(), inline=False)

		owner = self.bot.get_user(self.bot.config.get('primary_owner', self.bot.owner_id))
		embed.set_author(name=str(owner), icon_url=owner.avatar_url)

		embed.add_field(name='Servers', value=await self.bot.get_cog('Stats').guild_count())

		cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
		mem_usage = humanize.naturalsize(self.process.memory_full_info().uss)
		embed.add_field(name='Process', value=f'{mem_usage}\n{cpu_usage:.2f}% CPU')

		embed.add_field(name='Uptime', value=self.bot.cogs['BotBinMisc'].uptime(brief=True))
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
	@commands.cooldown(1, INVITE_DURATION_SECONDS, commands.BucketType.user)
	async def support(self, context):
		"""Directs you to the support server."""
		ch = self.bot.get_channel(self.bot.config['support_server'].get('invite_channel_id'))
		if ch is None:
			await context.send(_('This command is temporarily unavailable. Try again later?'))
			return

		reason = f'Created for {context.author} (ID: {context.author.id})'
		invite = await ch.create_invite(max_age=self.INVITE_DURATION_SECONDS, max_uses=self.MAX_INVITE_USES, reason=reason)

		try:
			await context.author.send(_('Official support server invite: {invite}').format(invite=invite))
		except discord.Forbidden:
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
		# XXX technically this will fail if the bot's client ID is not the same as its user ID
		# but fuck old apps just make a new one
		await context.send('<%s>' % discord.utils.oauth_url(self.bot.user.id, permissions))

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
		if module.startswith(self.__module__.split('.')[0]):
			# not a built-in command
			location = os.path.relpath(inspect.getfile(src)).replace('\\', '/')
			at = self._current_revision()
		elif module.startswith('discord'):
			source_url = 'https://github.com/Rapptz/discord.py'
			at = self._discord_revision()
			location = module.replace('.', '/') + '.py'
		else:
			if module.startswith('jishaku'):
				source_url = 'https://github.com/Gorialis/jishaku'
				at = self._pkg_version('jishaku')
			elif module.startswith('bot_bin'):
				source_url = 'https://github.com/bmintz/bot-bin'
				at = self._bot_bin_revision()

			location = module.replace('.', '/') + '.py'

		final_url = f'<{source_url}/blob/{at}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
		await context.send(final_url)

	@staticmethod
	def _current_revision(*, default='master'):
		repo = pygit2.Repository('.git')
		c = next(repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL))
		return c.hex[:10]

	@classmethod
	def _discord_revision(cls):
		version = cls._pkg_version('discord.py')
		version, sep, commit = version.partition('+g')
		return commit or 'v' + version

	@classmethod
	def _bot_bin_revision(cls, *, default='master'):
		ver = cls._pkg_version('bot_bin', default=default)
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
	if not bot.config['support_server'].get('invite_channel_id'):
		bot.remove_command('support')
