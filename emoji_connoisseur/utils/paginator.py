import asyncio
import collections
import contextlib

import discord

# Derived mainly from R.Danny but also from Liara:
# Copyright © 2015 Rapptz

# Copyright © 2016-2017 Pandentia and contributors
# https://github.com/Thessia/Liara/blob/75fa11948b8b2ea27842d8815a32e51ef280a999/cogs/utils/paginator.py

class CannotPaginate(Exception):
	pass

class Pages:
	"""Implements a paginator that queries the user for the
	pagination interface.

	Pages are 1-index based, not 0-index based.

	If the user does not reply within 2 minutes then the pagination
	interface exits automatically.

	Parameters
	------------
	ctx: Context
		The context of the command.
	entries: List[str]
		A list of entries to paginate.
	per_page: int
		How many entries show up per page.
	show_entry_count: bool
		Whether to show an entry count in the footer.
	timeout: float
		How long to wait for reactions on the message.
	delete_message: bool
		Whether to delete the message when the user presses the stop button.
	delete_message_on_timeout: bool
		Whether to delete the message after the reaction timeout is reached.

	Attributes
	-----------
	embed: discord.Embed
		The embed object that is being used to send pagination info.
		Feel free to modify this externally. Only the description
		and footer fields are internally modified.
	permissions: discord.Permissions
		Our permissions for the channel.
	text_message: Optional[str]
		What to display above the embed.
	"""
	def __init__(self, ctx, *, entries, per_page=7, show_entry_count=True, timeout=120.0,
		delete_message=True, delete_message_on_timeout=False,
	):
		self.bot = ctx.bot
		self.entries = entries
		self.message = ctx.message
		self.channel = ctx.channel
		self.author = ctx.author
		self.per_page = per_page
		pages, left_over = divmod(len(self.entries), self.per_page)
		if left_over:
			pages += 1
		self.maximum_pages = pages
		self.embed = discord.Embed()
		self.paginating = len(entries) > per_page
		self.show_entry_count = show_entry_count
		self.timeout = timeout
		self.delete_message = delete_message
		self.delete_message_on_timeout = delete_message_on_timeout
		self.text_message = None
		self.reaction_emojis = collections.OrderedDict((
			('\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.first_page),
			('\N{BLACK LEFT-POINTING TRIANGLE}', self.previous_page),
			('\N{BLACK RIGHT-POINTING TRIANGLE}', self.next_page),
			('\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.last_page),
			('\N{INPUT SYMBOL FOR NUMBERS}', self.numbered_page),
			('\N{BLACK SQUARE FOR STOP}', self.stop),
			('\N{INFORMATION SOURCE}', self.show_help),
		))

		if ctx.guild is not None:
			self.permissions = self.channel.permissions_for(ctx.guild.me)
		else:
			self.permissions = self.channel.permissions_for(ctx.bot.user)

		if not self.permissions.embed_links:
			raise CannotPaginate(_('Bot does not have embed links permission.'))

		if not self.permissions.send_messages:
			raise CannotPaginate(_('Bot cannot send messages.'))

		if self.paginating:
			# verify we can actually use the pagination session
			if not self.permissions.add_reactions:
				raise CannotPaginate(_('Bot does not have add reactions permission.'))

			if not self.permissions.read_message_history:
				raise CannotPaginate(_('Bot does not have Read Message History permission.'))

	def get_page(self, page):
		base = (page - 1) * self.per_page
		return self.entries[base:base + self.per_page]

	async def show_page(self, page, *, first=False):
		self.current_page = page
		entries = self.get_page(page)
		p = []
		for index, entry in enumerate(entries, 1 + ((page - 1) * self.per_page)):
			p.append(f'{index}. {entry}')

		if self.maximum_pages > 1:
			if self.show_entry_count:
				text = _('Page {page}⁄{self.maximum_pages} ({num_entries} entries)').format(
					num_entries=len(self.entries),
					**locals())
			else:
				text = _('Page {page}⁄{self.maximum_pages}').format(**locals())

			self.embed.set_footer(text=text)

		kwargs = {'embed': self.embed}
		if self.text_message:
			kwargs['content'] = self.text_message

		if not self.paginating:
			self.embed.description = '\n'.join(p)
			return await self.channel.send(**kwargs)

		if not first:
			self.embed.description = '\n'.join(p)
			await self.message.edit(**kwargs)
			return

		p.append('')
		p.append(_('Confused? React with \N{INFORMATION SOURCE} for more info.'))
		self.embed.description = '\n'.join(p)
		self.message = await self.channel.send(**kwargs)
		await self.add_reactions()

	async def add_reactions(self):
		for reaction in self.reaction_emojis:
			if self.maximum_pages == 2 and reaction in {'⏮', '⏭'}:
				# no |<< or >>| buttons if we only have two pages
				# we can't forbid it if someone ends up using it but remove
				# it from the default set
				continue

			with contextlib.suppress(discord.HTTPException):
				await self.message.add_reaction(reaction)

	async def checked_show_page(self, page):
		if page != 0 and page <= self.maximum_pages:
			await self.show_page(page)

	async def first_page(self):
		"""goes to the first page"""
		await self.show_page(1)

	async def last_page(self):
		"""goes to the last page"""
		await self.show_page(self.maximum_pages)

	async def next_page(self):
		"""goes to the next page"""
		await self.checked_show_page(self.current_page + 1)

	async def previous_page(self):
		"""goes to the previous page"""
		await self.checked_show_page(self.current_page - 1)

	async def show_current_page(self):
		if self.paginating:
			await self.show_page(self.current_page)

	async def numbered_page(self):
		"""lets you type a page number to go to"""

		to_delete = []
		to_delete.append(await self.channel.send(_('What page do you want to go to?')))

		def message_check(m):
			return m.author == self.author and \
				   self.channel == m.channel and \
				   m.content.isdigit()

		try:
			msg = await self.bot.wait_for('message', check=message_check, timeout=30.0)
		except asyncio.TimeoutError:
			to_delete.append(await self.channel.send(_('You took too long.')))
			await asyncio.sleep(5)
		else:
			page = int(msg.content)
			to_delete.append(msg)
			if page != 0 and page <= self.maximum_pages:
				await self.show_page(page)
			else:
				to_delete.append(await self.channel.send(_(
					'Invalid page given. ({page}/{self.maximum_pages})').format(**locals())))
				await asyncio.sleep(5)

		for message in to_delete:
			# we could use self.channel.delete_messages, but doing so would stop as soon as one of them fails
			# doing it this way ensures all of them are deleted
			with contextlib.suppress(discord.HTTPException):
				await message.delete()

	async def show_help(self):
		"""shows this message"""

		messages = [_('Welcome to the interactive paginator!\n')]
		messages.append(_('This interactively allows you to see pages of text by navigating with '
		                  'reactions. They are as follows:\n'))

		for emoji, func in self.reaction_emojis.items():
			messages.append(f'{emoji} {func.__doc__}')

		self.embed.description = '\n'.join(messages)
		self.embed.clear_fields()
		self.embed.set_footer(
			text=_('We were on page {self.current_page} before this message.').format(**locals()))
		await self.message.edit(embed=self.embed)

		async def go_back_to_current_page():
			await asyncio.sleep(60.0)
			await self.show_current_page()

		self.bot.loop.create_task(go_back_to_current_page())

	async def stop(self, *, delete=None):
		"""stops the interactive pagination session"""

		if delete is None:
			delete = self.delete_message

		if delete:
			with contextlib.suppress(discord.HTTPException):
				await self.message.delete()
		else:
			await self._clear_reactions()

		self.paginating = False

	async def _clear_reactions(self):
		try:
			await self.message.clear_reactions()
		except discord.Forbidden:
			for emoji in self.reaction_emojis:
				with contextlib.suppress(discord.HTTPException):
					await self.message.remove_reaction(emoji, self.message.author)
		except discord.HTTPException:
			pass

	def react_check(self, reaction, user):
		if user is None or user.id != self.author.id:
			return False

		if reaction.message.id != self.message.id:
			return False

		try:
			self.match = self.reaction_emojis[reaction.emoji]
		except KeyError:
			return False
		return True

	async def begin(self):
		"""Actually paginate the entries and run the interactive loop if necessary."""

		first_page = self.show_page(1, first=True)
		if not self.paginating:
			await first_page
		else:
			# allow us to react to reactions right away if we're paginating
			self.bot.loop.create_task(first_page)

		while self.paginating:
			try:
				reaction, user = await self.bot.wait_for(
					'reaction_add',
					check=self.react_check,
					timeout=self.timeout)
			except asyncio.TimeoutError:
				await self.stop(delete=self.delete_message_on_timeout)
				break

			await asyncio.sleep(0.2)
			with contextlib.suppress(discord.HTTPException):
				await self.message.remove_reaction(reaction, user)

			await self.match()

class FieldPages(Pages):
	"""
	Similar to Pages except entries should be a list of
	tuples having (key, value) to show as embed fields instead.
	"""

	async def show_page(self, page, *, first=False):
		self.current_page = page
		entries = self.get_page(page)

		self.embed.clear_fields()
		self.embed.description = discord.Embed.Empty

		for key, value in entries:
			self.embed.add_field(name=key, value=value, inline=False)

		if self.maximum_pages > 1:
			if self.show_entry_count:
				text = _('Page {page}⁄{self.maximum_pages} ({num_entries} entries)').format(
					num_entries=len(self.entries),
					**locals())
			else:
				text = _('Page {page}⁄{self.maximum_pages}').format(**locals())

			self.embed.set_footer(text=text)

		kwargs = {'embed': self.embed}
		if self.text_message:
			kwargs['content'] = self.text_message

		if not self.paginating:
			return await self.channel.send(**kwargs)

		if not first:
			await self.message.edit(**kwargs)
			return

		self.message = await self.channel.send(**kwargs)
		await self.add_reactions()

import itertools
import inspect
import re

# ?help
# ?help Cog
# ?help command
#	-> could be a subcommand

_mention = re.compile(r'<@\!?([0-9]{1,19})>')

def cleanup_prefix(bot, prefix):
	m = _mention.match(prefix)
	if m:
		user = bot.get_user(int(m.group(1)))
		if user:
			return f'@{user.name} '
	return prefix

async def _can_run(cmd, ctx):
	try:
		return await cmd.can_run(ctx)
	except:
		return False

def _command_signature(cmd):
	# this is modified from discord.py source
	# which I wrote myself lmao

	result = [cmd.qualified_name]
	if cmd.usage:
		result.append(cmd.usage)
		return ' '.join(result)

	params = cmd.clean_params
	if not params:
		return ' '.join(result)

	for name, param in params.items():
		if param.default is not param.empty:
			# We don't want None or '' to trigger the [name=value] case and instead it should
			# do [name] since [name=None] or [name=] are not exactly useful for the user.
			should_print = param.default if isinstance(param.default, str) else param.default is not None
			if should_print:
				result.append(f'[{name}={param.default!r}]')
			else:
				result.append(f'[{name}]')
		elif param.kind == param.VAR_POSITIONAL:
			result.append(f'[{name}...]')
		else:
			result.append(f'<{name}>')

	return ' '.join(result)

class HelpPaginator(Pages):
	def __init__(self, ctx, entries, *, per_page=4):
		super().__init__(ctx, entries=entries, per_page=per_page)
		self.reaction_emojis['\N{WHITE QUESTION MARK ORNAMENT}'] = self.show_bot_help
		self.total = len(entries)

	@classmethod
	async def from_cog(cls, ctx, cog):
		cog_name = cog.__class__.__name__

		# get the commands
		entries = sorted(ctx.bot.get_cog_commands(cog_name), key=lambda c: c.name)

		# remove the ones we can't run
		entries = [cmd for cmd in entries if (await _can_run(cmd, ctx)) and not cmd.hidden]

		self = cls(ctx, entries)
		self.title = _('{cog_name} Commands').format(**locals())
		self.description = inspect.getdoc(cog)
		self.prefix = cleanup_prefix(ctx.bot, ctx.prefix)

		return self

	@classmethod
	async def from_command(cls, ctx, command):
		try:
			entries = sorted(command.commands, key=lambda c: c.name)
		except AttributeError:
			entries = []
		else:
			entries = [cmd for cmd in entries if (await _can_run(cmd, ctx)) and not cmd.hidden]

		self = cls(ctx, entries)
		self.title = command.signature

		if command.description:
			self.description = f'{command.description}\n\n{command.help}'
		else:
			self.description = command.help or _('No help given.')

		self.prefix = cleanup_prefix(ctx.bot, ctx.prefix)
		return self

	@classmethod
	async def from_bot(cls, ctx):
		def key(c):
			return c.cog_name or '\u200b' + _('Misc')

		entries = sorted(ctx.bot.commands, key=key)
		nested_pages = []
		per_page = 9

		# 0: (cog, desc, commands) (max len == 9)
		# 1: (cog, desc, commands) (max len == 9)
		# ...

		for cog, commands in itertools.groupby(entries, key=key):
			plausible = [cmd for cmd in commands if (await _can_run(cmd, ctx)) and not cmd.hidden]
			if len(plausible) == 0:
				continue

			description = ctx.bot.get_cog(cog)
			if description is None:
				description = discord.Embed.Empty
			else:
				description = inspect.getdoc(description) or discord.Embed.Empty

			nested_pages.extend((cog, description, plausible[i:i + per_page]) for i in range(0, len(plausible), per_page))

		self = cls(ctx, nested_pages, per_page=1) # this forces the pagination session
		self.prefix = cleanup_prefix(ctx.bot, ctx.prefix)

		# swap the get_page implementation with one that supports our style of pagination
		self.get_page = self.get_bot_page
		self._is_bot = True

		# replace the actual total
		self.total = sum(len(o) for __, __, o in nested_pages)
		return self

	def get_bot_page(self, page):
		cog, description, commands = self.entries[page - 1]
		self.title = _('{cog} Commands').format(**locals())
		self.description = description
		return commands

	async def show_page(self, page, *, first=False):
		self.current_page = page
		entries = self.get_page(page)

		self.embed.clear_fields()
		self.embed.description = self.description
		self.embed.title = self.title

		if hasattr(self, '_is_bot'):
			invite = f'https://discord.gg/{self.bot.config["support_server_invite_code"]}'
			value = _('For more help, join the official bot support server: {invite}').format(**locals())
			self.embed.add_field(name='Support', value=value, inline=False)

		self.embed.set_footer(
			text=_('Use "{self.prefix}help command" for more info on a command.').format(**locals()))

		signature = _command_signature

		for entry in entries:
			self.embed.add_field(
				name=signature(entry),
				value=entry.short_doc or _("No help given"),
				inline=False)

		if self.maximum_pages:
			self.embed.set_footer(
				text=_('Page {page}⁄{self.maximum_pages} ({self.total} commands)').format(**locals()))

		if not self.paginating:
			return await self.channel.send(embed=self.embed)

		if not first:
			await self.message.edit(embed=self.embed)
			return

		self.message = await self.channel.send(embed=self.embed)
		await self.add_reactions()

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

		self.embed.title = 'Using the bot'
		self.embed.description = 'Hello! Welcome to the help page.'
		self.embed.clear_fields()

		argument = _('argument')

		self.embed.add_field(
			name=_('How do I use this bot?'), value=_('Reading the bot signature is pretty simple.'))

		entries = (
			(f'<{argument}>', _('This means the argument is __**required**__.')),
			(f'[{argument}]', _('This means the argument is __**optional**__.')),
			(_('[A|B]'), _('This means that it can be __**either A or B**__.')),
			(f'[{argument}...]', _('This means you can have multiple arguments.\n'
			                       'Now that you know the basics, it should be noted that...\n'
			                       '__**You do not type in the brackets!**__'))
		)

		for name, value in entries:
			self.embed.add_field(name=name, value=value, inline=False)

		self.embed.set_footer(
			text=_('We were on page {self.current_page} before this message.').format(**locals()))
		await self.message.edit(embed=self.embed)

		async def go_back_to_current_page():
			await asyncio.sleep(30.0)
			await self.show_current_page()

		self.bot.loop.create_task(go_back_to_current_page())
