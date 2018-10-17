#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import collections
import contextlib
import io
import logging
import re
import traceback
import weakref

import aiohttp
import asyncpg
import discord
from discord.ext import commands

from .db import DatabaseEmote
from .. import utils
from ..utils import image as image_utils
from ..utils import checks
from ..utils import errors
from ..utils.paginator import CannotPaginate, Pages

logger = logging.getLogger(__name__)

class Emotes:
	"""Commands related to the main functionality of the bot"""

	def __init__(self, bot):
		self.bot = bot
		self.db = self.bot.get_cog('Database')
		self.logger = self.bot.get_cog('Logger')
		self.http = aiohttp.ClientSession(loop=self.bot.loop, read_timeout=30, headers={
			'User-Agent':
				self.bot.config['user_agent'] + ' '
				+ self.bot.http.user_agent
		})

		# Keep track of replies so that if the user edits/deletes a message,
		# we delete/edit the corresponding reply.
		# Each message supposedly takes up about 256 bytes of RAM.
		# Don't store more than 1MiB of them.
		self.replies = utils.LRUDict(size=1024**2//256)

		# keep track of created paginators so that we can remove their reaction buttons on unload
		self.paginators = weakref.WeakSet()

	def __unload(self):
		async def task():
			# aiohttp can't decide if this should be a coroutine...
			# i think it shouldn't be, since it never awaits
			await self.http.close()

			for paginator in self.paginators:
				await paginator.stop(delete=False)

		self.bot.loop.create_task(task())

	## Commands

	@commands.command()
	@checks.not_blacklisted()
	async def info(self, context, emote: DatabaseEmote):
		"""Gives info on an emote.

		The emote must be in the database.
		"""
		embed = discord.Embed()

		if emote.preserve:
			embed.title = _('{emote} (Preserved)').format(emote=emote.with_name())
		else:
			embed.title = emote.with_name()

		if emote.description is not None:
			embed.description = emote.description

		if emote.created is not None:
			embed.timestamp = emote.created
			embed.set_footer(text=_('Created'))

		avatar = None
		with contextlib.suppress(AttributeError):
			avatar = self.bot.get_user(emote.author).avatar_url_as(static_format='png', size=32)

		name = utils.format_user(self.bot, emote.author, mention=False)
		if avatar is None:
			embed.set_author(name=name)
		else:
			embed.set_author(name=name, icon_url=avatar)

		if emote.modified is not None:
			embed.add_field(
				name=_('Last modified'),
				# hangul filler prevents the embed fields from jamming next to each other
				value=utils.format_time(emote.modified) + '\N{hangul filler}')

		embed.add_field(name='Usage count', value=await self.db.get_emote_usage(emote))

		await context.send(embed=embed)

	@commands.command()
	@checks.not_blacklisted()
	async def count(self, context):
		"""Tells you how many emotes are in my database."""
		static, animated, total = await self.db.count()
		static_cap, animated_cap, total_cap = self.db.capacity()
		await context.send(_(
			'Static emotes: **{static} ⁄ {static_cap}**\n'
			'Animated emotes: **{animated} ⁄ {animated_cap}**\n'
			'**Total: {total} ⁄ {total_cap}**').format(**locals()))

	@commands.command()
	@checks.not_blacklisted()
	async def big(self, context, emote: DatabaseEmote):
		"""Shows the original image for the given emote."""
		await context.send(f'{emote.name}: {emote.url}')

	@commands.command(rest_is_raw=True)
	@checks.not_blacklisted()
	async def quote(self, context, *, message):
		"""Quotes your message, with :foo: and ;foo; replaced with their emote forms"""
		if not message:
			return

		message, has_emotes = await self.quote_emotes(context.message, message)

		if self.bot.has_permissions(context.message, manage_messages=True):
			# no space because rest_is_raw preserves the space after "ec/quote"
			message = _('{context.author.mention} said:').format(**locals()) + message

			# it doesn't matter if they deleted their message before we sent our reply
			with contextlib.suppress(discord.NotFound):
				await context.message.delete()

		reply = await context.send(message)
		self.replies[context.message.id] = 1, reply

	@commands.command(aliases=['create'], usage='[name] <image URL or custom emote>')
	@checks.not_blacklisted()
	async def add(self, context, *args):
		"""Add a new emote to the bot.

		You can use it like this:
		`ec/add :thonkang:` (if you already have that emote)
		`ec/add rollsafe https://image.noelshack.com/fichiers/2017/06/1486495269-rollsafe.png`
		`ec/add speedtest <https://cdn.discordapp.com/emojis/379127000398430219.png>`

		With a file attachment:
		`ec/add name` will upload a new emote using the first attachment as the image and call it `name`
		`ec/add` will upload a new emote using the first attachment as the image,
		and its filename as the name
		"""
		if context.message.webhook_id or context.author.bot:
			return await context.send(_(
				'Sorry, webhooks and bots may not add emotes. '
				'Go find a human to do it for you.'))

		name, url = self.parse_add_command_args(context, args)
		async with context.typing():
			message = await self.add_safe(name.strip(':;'), url, context.message.author.id)
		await context.send(message)

	def parse_add_command_args(self, context, args):
		if context.message.attachments:
			return self.parse_add_command_attachment(context, args)

		elif len(args) == 1:
			match = re.match(utils.lexer.t_CUSTOM_EMOTE, args[0])
			if match is None:
				raise commands.BadArgument(_(
					'Error: I expected a custom emote as the first argument, '
					'but I got something else. '
					"If you're trying to add an emote using an image URL, "
					'you need to provide a name as the first argument, like this:\n'
					'`{}add NAME_HERE URL_HERE`').format(context.prefix))
			else:
				url = utils.emote.url(match['id'], animated=match['animated'])

			return match['name'], url

		elif len(args) >= 2:
			name = args[0]
			match = re.match(utils.lexer.t_CUSTOM_EMOTE, args[1])
			if match is None:
				url = utils.strip_angle_brackets(args[1])
			else:
				url = utils.emote.url(match['id'], animated=match['animated'])

			return name, url

		elif not args:
			raise commands.BadArgument(_('Your message had no emotes and no name!'))

	@staticmethod
	def parse_add_command_attachment(context, args):
		attachment = context.message.attachments[0]
		# as far as i can tell, this is how discord replaces filenames when you upload an emote image
		name = ''.join(args) if args else attachment.filename.split('.')[0].replace(' ', '')
		url = attachment.url

		return name, url

	async def add_safe(self, name, url, author_id):
		"""Try to add an emote. Returns a string that should be sent to the user."""
		try:
			emote = await self.add_from_url(name, url, author_id)
		except errors.ConnoisseurError as ex:
			return str(ex)
		except discord.HTTPException as ex:
			return (
				_('An error occurred while creating the emote:\n')
				+ utils.format_http_exception(ex))
		except ValueError:
			return _('Error: Invalid URL.')
		else:
			return _('Emote {emote} successfully created.').format(emote=emote)

	async def add_from_url(self, name, url, author_id):
		# db.create_emote already does this, but do it again here so that we can fail early
		# in case resizing takes a long time.
		await self.db.ensure_emote_does_not_exist(name)

		try:
			image_data = await self.fetch_emote(url)
		except asyncio.TimeoutError:
			raise errors.URLTimeoutError

		emote = await self.create_emote_from_bytes(name, author_id, image_data, verify=False)

		return emote

	async def fetch_emote(self, url):
		# credits to @Liara#0001 (ID 136900814408122368) for most of this part
		# https://gitlab.com/Pandentia/element-zero/blob/47bc8eeeecc7d353ec66e1ef5235adab98ca9635/element_zero/cogs/emoji.py#L217-228

		def validate_headers(response):
			if response.reason != 'OK':
				raise errors.HTTPException(response.status)
			content_type = response.headers.get('Content-Type')
			if content_type and content_type not in {'image/png', 'image/jpeg', 'image/gif'}:
				raise errors.InvalidImageError

		try:
			async with self.http.head(url, timeout=5) as response:
				validate_headers(response)
		except aiohttp.ServerDisconnectedError as exception:
			validate_headers(exception.message)

		async with self.http.get(url) as response:
			validate_headers(response)
			return io.BytesIO(await response.read())

	async def create_emote_from_bytes(self, name, author_id, image_data: io.BytesIO, *, verify=True):
		if verify:
			await self.db.ensure_emote_does_not_exist(name)

		animated = image_utils.is_animated(image_data.getvalue())

		try:
			image_data = await image_utils.resize_until_small(image_data)
		except asyncio.TimeoutError:
			raise errors.ImageResizeTimeoutError

		emote = await self.db.create_emote(name, author_id, animated, image_data.read())
		self.bot.dispatch('emote_add', emote)
		return emote

	@commands.command(aliases=['delete', 'delet', 'del', 'rm'])
	async def remove(self, context, *names: commands.clean_content):
		"""Removes one or more emotes from the bot. You must own all of them."""
		if not names:
			return await context.send(_('Error: you must provide the name of at least one emote to remove'))
		messages = {}

		async with context.typing():
			for name in names:
				arg = f'\\:{name}:'

				try:
					emote = await self.db.get_emote(name)
				except BaseException as error:
					messages.setdefault(self._humanize_errors(error), []).append(arg)
					continue

				# log the emote removal *first* because if we were to do it afterwards,
				# the emote would not display (since it's already removed)
				removal_message = await self.logger.on_emote_remove(emote)
				try:
					await self.db.remove_emote(emote, context.author.id)
				except (errors.ConnoisseurError, errors.DiscordError) as error:
					messages.setdefault(self._humanize_errors(error), []).append(arg)
					# undo the log
					with contextlib.suppress(AttributeError):
						await removal_message.delete()
				else:
					message = _('**Successfully deleted:**')
					messages.setdefault((0, message), []).append(emote.escaped_name())

		messages = self._sort_errors(messages)
		message = self._format_errors(messages)
		await context.send(message)

	@commands.command(name='steal-these', hidden=True)
	@checks.not_blacklisted()
	async def steal_these(self, context, *emotes):
		"""Steal a bunch of custom emotes."""

		# format is: {(order, error_message_format_string): emotes_that_had_that_error}
		# no error: key=None
		# HTTP error: key=HTTP status code
		messages = {}
		# we could use *emotes: discord.PartialEmoji here but that would require spaces between each emote.
		# and would fail if any arguments were not valid emotes
		for match in re.finditer(utils.lexer.t_CUSTOM_EMOTE, ''.join(emotes)):
			animated, name, id = match.groups()
			image_url = utils.emote.url(id, animated=animated)
			async with context.typing():
				arg = f'\\:{name}:'

				try:
					emote = await self.add_from_url(name, image_url, context.author.id)
				except BaseException as error:
					messages.setdefault(self._humanize_errors(error), []).append(arg)
				else:
					messages.setdefault((0, _('**Successfully created:**')), []).append(str(emote))

		if not messages:
			return await context.send(_('Error: no existing custom emotes were provided.'))

		messages = self._sort_errors(messages)
		message = self._format_errors(messages)
		await context.send(message)

	@staticmethod
	def _humanize_errors(error=None):
		if isinstance(error, errors.EmoteExistsError):
			return 1, _('**Already exists:**')
		if isinstance(error, errors.EmoteNotFoundError):
			# same priority as EmoteExists
			return 1, _('**Not found:**')
		if isinstance(error, (discord.HTTPException, errors.HTTPException)):
			return 2, _('**Server returned error code {error.status}:**').format(error=error)
		if isinstance(error, asyncio.TimeoutError):
			return 3, _('**Took too long to retrieve or resize:**')
		if isinstance(error, errors.NoMoreSlotsError):
			return 4, _('**Failed because I ran out of backend servers:**')

		# unhandled errors are still errors
		raise error

	@staticmethod
	def _sort_errors(errors: collections.abc.Mapping):
		# order by success first then errors
		def sort_key(pair):
			(sort_order, message), arguments = pair
			return sort_order

		return sorted(errors.items(), key=sort_key)

	@staticmethod
	def _format_errors(messages):
		message = io.StringIO()
		for (sort_order, error_message), arguments in messages:
			message.write(f'{error_message} ({len(arguments)})\n')
			message.write(' '.join(arguments))
			message.write('\n\n')
		return utils.fix_first_line(message.getvalue())

	@commands.command(aliases=['mv'])
	async def rename(self, context, *args):
		"""Renames an emote. You must own it.

		Example:
		ec/rename a b
		Renames \:a: to \:b:
		"""

		if not args:
			return await context.send(_('You must specify an old name and a new name.'))

		# allow e.g. foo{bar,baz} -> rename foobar to foobaz
		if len(args) == 1:
			old_name, new_name = utils.expand_cartesian_product(args[0])
			if not new_name:
				return await context.send(_('Error: you must provide a new name for the emote.'))
		else:
			old_name, new_name, *rest = args

		old_name, new_name = map(lambda c: c.strip(':;'), (old_name, new_name))

		try:
			await self.db.rename_emote(old_name, new_name, context.author.id)
		except discord.HTTPException as ex:
			await context.send(utils.format_http_exception(ex))
		else:
			await context.send(_('Emote successfully renamed.'))

	@commands.command()
	async def describe(self, context, name, *, description=None):
		"""Set an emote's description. It will be displayed in ec/info.

		If you leave out the description, it will be removed.
		You could use this to:
		- Detail where you got the image
		- Credit another author
		- Write about why you like the emote
		- Describe how it's used
		Currently, there's a limit of 500 characters.
		"""
		await self.db.set_emote_description(name, context.author.id, description)
		await context.try_add_reaction(utils.SUCCESS_EMOJIS[True])

	@commands.command()
	@checks.not_blacklisted()
	async def react(self, context, emote: DatabaseEmote, *, message: utils.converter.Message = None):
		"""Add a reaction to a message. Sad reacts only please.

		To specify the message, either provide a keyword to search for, or a message ID.
		If you don't specify a message, the last message sent in this channel will be chosen.
		Otherwise, the first message matching the keyword will be reacted to.
		"""

		if not await self._check_reaction_permissions(context):
			return

		if message is None:
			# get the second to last message (ie ignore the invoking message)
			message = await utils.get_message_by_offset(context.channel, -2)

		# there's no need to react to a message if that reaction already exists
		def same_emote(reaction):
			return getattr(reaction.emoji, 'id', None) == emote.id

		if discord.utils.find(same_emote, message.reactions):
			return await context.send(_(
				'You can already react to that message with that emote.'),
				delete_after=5)

		try:
			await message.add_reaction(emote.as_reaction())
		except discord.Forbidden:
			return await context.send(_('Unable to react: permission denied.'))
		except discord.HTTPException:
			return await context.send(_('Unable to react. Discord must be acting up.'))

		instruction_message = await context.send(_(
			"OK! I've reacted to that message. "
			"Please add your reaction now."))

		def check(payload):
			return (
				payload.message_id == message.id
				and payload.user_id == context.message.author.id
				and emote.id == getattr(payload.emoji, 'id', None))	 # unicode emoji have no id

		try:
			await self.bot.wait_for('raw_reaction_add', timeout=30, check=check)
		except asyncio.TimeoutError:
			pass
		else:
			await self.db.log_emote_use(emote.id, context.author.id)
		finally:
			# if we don't sleep, it would appear that the bot never un-reacted
			# i.e. the reaction button would still say "2" even after we remove our reaction
			# in my testing, 0.2s is the minimum amount of time needed to work around this.
			# unfortunately, if you look at the list of reactions, it still says the bot reacted.
			# no amount of sleeping can fix that, in my tests.
			await asyncio.sleep(0.2)
			await message.remove_reaction(emote.as_reaction(), self.bot.user)

			for message in context.message, instruction_message:
				with contextlib.suppress(discord.HTTPException):
					await message.delete()

	async def _check_reaction_permissions(self, context):
		# author might not be a Member, even in a guild, if it's a webhook.
		if not context.guild or not isinstance(context.author, discord.Member):
			return True

		sender_permissions = context.channel.permissions_for(context.author)
		permissions = context.channel.permissions_for(context.guild.me)

		if not sender_permissions.read_message_history or not permissions.read_message_history:
			await context.send(_('Unable to react: you and I both need permission to read message history.'))
			return False
		if not sender_permissions.add_reactions or not permissions.add_reactions:
			await context.send(_('Unable to react: you and I both need permission to add reactions.'))
			return False
		if not sender_permissions.external_emojis or not permissions.external_emojis:
			await context.send(_('Unable to react: you and I both need permission to use external emotes.'))
			return False

		return True

	@commands.command(aliases=('ls', 'dir'))
	async def list(self, context, *, user: discord.User = None):
		"""List all emotes the bot knows about.
		If a user is provided, the list will only contain emotes created by that user.
		"""
		processed = []

		args = []
		if user is not None:
			args.append(user.id)

		async for emote in self.db.all_emotes(*args):
			author = utils.format_user(self.bot, emote.author, mention=True)

			if emote.preserve:
				processed.append(
					_('{emote} (Preserved) — owned by {author}').format(
						emote=emote.with_name(),
						author=author))
			else:
				processed.append(
					_('{emote} — owned by {author}').format(emote=emote.with_name(), author=author))

		if not processed:
			if not user:
				return await context.send(_('No emotes have been created yet. Be the first!'))

			if user == context.author:
				return await context.send(_('You have not created any emotes yet.'))

			return await context.send(_('That person has not created any emotes yet.'))

		paginator = Pages(context, entries=processed)
		self.paginators.add(paginator)

		if self.bot.config['website']:
			end_path = f'/{user.id}' if user else ''
			paginator.text_message = _('Also check out the list website at {website}.').format(
				website=f'{self.bot.config["website"]}/list{end_path}')

		await paginator.begin()

	@commands.command(aliases=['find'])
	async def search(self, context, query):
		"""Search for emotes whose name contains "query"."""

		processed = []

		async for emote in self.db.search(query):
			processed.append(emote.with_name())

		if not processed:
			return await context.send(_('No results matched your query.'))

		paginator = Pages(context, entries=processed)
		self.paginators.add(paginator)
		await paginator.begin()

	@commands.command()
	async def popular(self, context):
		"""Lists popular emojis."""

		# code generously provided by @Liara#0001 under the MIT License:
		# https://gitlab.com/Pandentia/element-zero/blob/ca7d7f97e068e89334e66692922d9a8744e3e9be/element_zero/cogs/emoji.py#L364-399
		processed = []

		async for i, emote in utils.async_enumerate(self.db.popular_emotes(limit=200)):
			c = emote.usage
			multiple = '' if c == 1 else 's'

			# TODO internationalize this (needs plural support)
			processed.append(
				f'{emote.with_name()} '
				f'— used {c} time{multiple}')

		if not processed:
			return await context.send(_('No emotes have been created yet. Be the first!'))

		paginator = Pages(context, entries=processed)
		self.paginators.add(paginator)
		await paginator.begin()

	@commands.command(hidden=True)
	@commands.is_owner()
	async def recover(self, context, message_id):
		"""recovers a decayed or removed emote from the log channel.

		message_id is the ID of the log message.
		"""

		try:
			channel = self.bot.get_cog('Logger').channel
		except AttributeError:
			return await context.send(_('Logger cog not loaded.'))

		try:
			message = await channel.get_message(message_id)
		except discord.NotFound:
			return await context.send(_('Message not found.'))

		try:
			description = message.embeds[0].description
		except IndexError:
			return await context.send(_('No embeds were found in that message.'))

		try:
			emote = re.match(utils.lexer.t_CUSTOM_EMOTE, description)
		except TypeError:
			return await context.send(_('No description was found in that embed.'))
		name = emote['name']

		try:
			url = utils.emote.url(emote['id'], animated=emote['animated'])
		except AttributeError:
			return await context.send(_("No custom emotes were found in that embed's description."))

		try:
			author = int((
				re.search(r'<@!?(\d{17,})>', description)
				or re.search('Unknown user with ID (\d{17,})', description))[1])
		except AttributeError:
			return await context.send(_('No author IDs were found in that embed.'))

		message = await self.add_safe(name, url, author)
		await context.send(message)

	@commands.command()
	async def toggle(self, context):
		"""Toggles the emote auto response (;name;) for you.
		This is global, ie it affects all servers you are in.

		If a guild has been set to opt in, you will need to run this command before I can respond to you.
		"""
		guild = None
		if context.guild is not None:
			guild = context.guild.id
		if await self.db.toggle_user_state(context.author.id, guild):
			await context.send(_('Opted in to the emote auto response.'))
		else:
			await context.send(_('Opted out of the emote auto response.'))

	@commands.command(name='toggleserver')
	@checks.owner_or_permissions(manage_emojis=True)
	@commands.guild_only()
	async def toggle_guild(self, context):
		"""Toggle the auto response for this server.
		If you have never run this command before, this server is opt-out: the emote auto response is
		on for all users, except those who run ec/toggle.

		If this server is opt-out, the emote auto response is off for all users,
		and they must run ec/toggle before the bot will respond to them.

		Opt in mode is useful for very large servers where the bot's response would be annoying or
		would conflict with that of other bots.
		"""
		if await self.db.toggle_guild_state(context.guild.id):
			await context.send(_('Emote auto response is now opt-out for this server.'))
		else:
			await context.send(_('Emote auto response is now opt-in for this server.'))

	@commands.command()
	@commands.is_owner()
	async def blacklist(self, context, user: discord.Member, *,
		reason: commands.clean_content(
			fix_channel_mentions=True,
			escape_markdown=True,
			use_nicknames=False
		) = None
	):
		"""Prevent a user from using commands and the emote auto response.
		If you don't provide a reason, the user will be un-blacklisted."""
		await self.db.set_user_blacklist(user.id, reason)
		if reason is None:
			await context.send(_('User un-blacklisted.'))
		else:
			await context.send(_('User blacklisted with reason "{reason}".').format(**locals()))

	@commands.command(hidden=True)
	@commands.is_owner()
	async def preserve(self, context, should_preserve: bool, *names: commands.clean_content):
		"""Sets preservation status of emotes."""
		names = set(names)
		messages = {}
		success_message = (
			_('**Succesfully preserved:**')
			if should_preserve else
			_('**Succesfully un-preserved:**'))
		for name in names:
			try:
				emote = await self.db.set_emote_preservation(name, should_preserve)
			except errors.EmoteNotFoundError as ex:
				messages.setdefault(self._humanize_errors(ex), []).append(f'\\:{name}:')
			else:
				messages.setdefault((0, success_message), []).append(str(emote))
				self.bot.dispatch(f'emote_{"un" if not should_preserve else ""}preserve', emote)

		messages = self._sort_errors(messages)
		message = self._format_errors(messages)
		await context.send(message)

	## Events

	@staticmethod
	async def on_command_error(context, error):
		if isinstance(error, (errors.ConnoisseurError, CannotPaginate)):
			await context.send(error)

	async def on_message(self, message):
		"""Reply to messages containing :name: or ;name; with the corresponding emotes.
		This is like half the functionality of the bot
		"""

		if not await self._should_auto_reply(message):
			return

		reply, has_emotes = await self.extract_emotes(message, log_usage=True)
		if not has_emotes:
			return

		self.replies[message.id] = 0, await message.channel.send(reply)

	async def _should_auto_reply(self, message: discord.Message):
		"""return whether the bot should send an emote auto response to message"""

		if not self.bot.should_reply(message):
			return False

		context = await self.bot.get_context(message)
		if context.valid:
			# user invoked a command, rather than the emote auto response
			# so don't respond a second time
			return False

		if not self.bot.has_permissions(message, external_emojis=True):
			return False

		if message.guild:
			guild = message.guild.id
		else:
			guild = None

		await self.bot.db_ready.wait()

		if not await self.db.get_state(guild, message.author.id):
			return False

		return True

	async def on_raw_message_edit(self, payload):
		"""Ensure that when a message containing emotes is edited, the corresponding emote reply is, too."""
		# data = https://discordapp.com/developers/docs/resources/channel#message-object
		if payload.message_id not in self.replies or 'content' not in payload.data:
			return

		message = discord.Message(
			state=self.bot._connection,
			channel=self.bot.get_channel(int(payload.data['channel_id'])),
			data=payload.data)

		type, reply = self.replies[payload.message_id]
		if type == 0:  # extract_emotes
			await self._handle_extracted_edit(message, reply)
		else:
			await self._handle_quoted_edit(message, reply)

	async def _handle_extracted_edit(self, message, reply):
		"""handle the case when a user edits a message that we auto-responded to"""
		emotes, message_has_emotes = await self.extract_emotes(message, log_usage=False)

		# editing out emotes from a message deletes the reply
		if not message_has_emotes:
			del self.replies[message.id]
			return await reply.delete()
		elif emotes == reply.content:
			# don't edit a message if we don't need to
			return

		await reply.edit(content=emotes)

	async def _handle_quoted_edit(self, message, reply):
		"""handle the case when the user edits an ec/quote invocation"""
		context = await self.bot.get_context(message)
		content = context.view.read_rest()
		if not context.command or not context.command is self.quote or not content:
			del self.replies[message.id]
			return await reply.delete()

		emotes, message_has_emotes = await self.quote_emotes(
			message,
			content,
			log_usage=False)
		if emotes == reply.content:
			# don't edit a message if we don't need to
			return

		await reply.edit(content=emotes)

	async def _extract_emotes(self,
		message: discord.Message,
		content: str = None,
		*,
		callback,
		log_usage=False,
	):
		"""Extract emotes according to predicate.
		Callback is a coroutine function taking three arguments: token, out: StringIO, and emotes_used: set
		For each token, callback will be called with these arguments.
		out is the StringIO that holds the extracted string to return, and emotes_used is a set
		containing the IDs of all emotes that were used, for logging purposes.

		Returns extracted_message: str, has_emotes: bool.
		"""

		out = io.StringIO()
		emotes_used = set()

		if content is None:
			content = message.content

		# we make a new one each time otherwise two tasks might use the same lexer at the same time
		lexer = utils.lexer.new()

		lexer.input(content)
		for toke1 in iter(lexer.token, None):
			await callback(toke1, out, emotes_used)

		result = out.getvalue() if emotes_used else content

		if log_usage:
			for emote in emotes_used:
				await self.db.log_emote_use(emote, message.author.id)

		return utils.clean_content(self.bot, message, result), bool(emotes_used)

	async def extract_emotes(self, message: discord.Message, content: str = None, *, log_usage=False):
		"""Parse all emotes (:name: or ;name;) from a message"""

		async def callback(toke1, out, emotes_used):
			if toke1.type == 'TEXT' and toke1.value == '\n':
				return out.write(toke1.value)
			if not self._is_emote(toke1):
				return

			try:
				emote = await self.db.get_emote(toke1.value.strip(':;'))
			except errors.EmoteNotFoundError:
				pass
			else:
				out.write(str(emote))
				emotes_used.add(emote.id)

		extracted, has_emotes = await self._extract_emotes(
			message,
			content,
			callback=callback,
			log_usage=log_usage)

		return utils.fix_first_line(extracted.strip()), has_emotes

	async def quote_emotes(self, message: discord.Message, content: str = None, *, log_usage=False):
		"""Parse all emotes (:name: or ;name;) from a message, preserving non-emote text"""

		async def callback(toke1, out, emotes_used):
			if not self._is_emote(toke1):
				return out.write(toke1.value)

			try:
				emote = await self.db.get_emote(toke1.value.strip(':;'))
			except errors.EmoteNotFoundError:
				out.write('\\'+toke1.value)
			else:
				out.write(str(emote))
				emotes_used.add(emote.id)

		return await self._extract_emotes(message, content, callback=callback, log_usage=log_usage)

	@classmethod
	def _is_emote(cls, toke1):
		return toke1.type == 'EMOTE' and toke1.value.strip(':') not in utils.emote.emoji_shortcodes

	async def delete_reply(self, message_id):
		"""Delete our reply to a message containing emotes."""
		try:
			type, message = self.replies.pop(message_id)
		except KeyError:
			return

		with contextlib.suppress(discord.HTTPException):
			await message.delete()

	async def on_raw_message_delete(self, payload):
		"""Ensure that when a message containing emotes is deleted, the emote reply is, too."""
		await self.delete_reply(payload.message_id)

	async def on_raw_bulk_message_delete(self, payload):
		# TODO use bot.delete_messages
		for message_id in payload.message_ids:
			await self.delete_reply(message_id)

def setup(bot):
	bot.add_cog(Emotes(bot))
