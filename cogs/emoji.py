#!/usr/bin/env python3.6
# encoding: utf-8

import asyncio
import imghdr
from io import BytesIO, StringIO
import itertools
import logging
import re
import traceback
import weakref

import aiohttp
import asyncpg
import discord
from discord.ext import commands
from wand.image import Image

from cogs.db import DatabaseEmote
import utils
from utils import async_enumerate
from utils import checks
from utils import errors
from utils import HistoryMessage
from utils.paginator import ListPaginator

logger = logging.getLogger('cogs.emoji')


class Emotes:
	"""Commands related to the main functionality of the bot"""

	"""Matches :foo: and ;foo; but not :foo;. Used for emotes in text."""
	RE_EMOTE = re.compile(r'(:|;)(?P<name>\w{2,32})\1|(?P<newline>\n)', re.ASCII)

	"""Matches only custom server emoji."""
	RE_CUSTOM_EMOTE = re.compile(r'<(?P<animated>a?):(?P<name>\w{2,32}):(?P<id>\d{17,})>', re.ASCII)

	"""Matches code blocks, which should be ignored."""
	RE_CODE = re.compile(r'(`{1,3}).+?\1', re.DOTALL)

	def __init__(self, bot):
		self.bot = bot
		self.utils = self.bot.get_cog('Utils')
		self.db = self.bot.get_cog('Database')
		self.logger = self.bot.get_cog('Logger')
		self.http = aiohttp.ClientSession(loop=self.bot.loop, read_timeout=30, headers={
			'User-Agent':
				'EmojiConnoisseurBot (https://github.com/bmintz/emoji-connoisseur) '
				+ self.bot.http.user_agent
		})

		# Keep track of replies so that if the user edits/deletes a message,
		# we delete/edit the corresponding reply.
		# Don't store too many of these replies.
		# TODO investigate how much RAM this dict actually uses. (sys.getsizeof)
		self.replies = utils.LRUDict(size=1000)

		# keep track of created paginators so that we can remove their reaction buttons on unload
		self.paginators = weakref.WeakSet()

	def __unload(self):
		# aiohttp can't decide if this should be a coroutine...
		# i think it shouldn't be, since it never awaits
		self.bot.loop.create_task(self.http.close())
		for paginator in self.paginators:
			self.bot.loop.create_task(paginator.stop())

	## COMMANDS

	@commands.command()
	@checks.not_blacklisted()
	async def info(self, context, emote: DatabaseEmote):
		"""Gives info on an emote.

		The emote must be in the database.
		"""
		embed = discord.Embed()

		title = str(emote)
		if emote['preserve']: title += ' (Preserved)'
		embed.title = title

		if emote['description'] is not None:
			embed.description = emote['description']

		if emote['created'] is not None:
			embed.timestamp = emote['created']
			embed.set_footer(text='Created')

		avatar = None
		try:
			avatar = self.bot.get_user(emote['author']).avatar_url_as(static_format='png', size=32)
		except AttributeError:
			pass

		name = self.utils.format_user(emote['author'], mention=False)
		if avatar is None:
			embed.set_author(name=name)
		else:
			embed.set_author(name=name, icon_url=avatar)

		if emote['modified'] is not None:
			embed.add_field(
				name='Last modified',
				# hangul filler prevents the embed fields from jamming next to each other
				value=self.utils.format_time(emote['modified']) + '\N{hangul filler}')

		embed.add_field(name='Usage count', value=await self.db.get_emote_usage(emote))

		await context.send(embed=embed)

	@commands.command()
	@checks.not_blacklisted()
	async def count(self, context):
		"""Tells you how many emotes are in my database."""
		static, animated, total = await self.db.count()
		message = (
			f'Static emotes: {static}\n'
			f'Animated emotes: {animated}\n'
			f'Total: {total}')
		await context.send(self.utils.fix_first_line(message))

	@commands.command()
	@checks.not_blacklisted()
	async def big(self, context, emote: DatabaseEmote):
		"""Shows the original image for the given emote"""
		embed = discord.Embed(title=emote['name'])
		embed.set_image(url=emote.url)
		await context.send(embed=embed)

	@commands.command(aliases=['create'])
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
		if context.message.attachments:
			attachment = context.message.attachments[0]
			# as far as i can tell, this is how discord replaces filenames when you upload an emote image
			name = ''.join(args) if args else attachment.filename.split('.')[0].replace(' ', '')
			url = attachment.url

		elif len(args) == 1:
			match = self.RE_CUSTOM_EMOTE.match(args[0])
			if match is None:
				return await context.send(
					'Error: I expected a custom emote as the first argument, '
					'but I got something else. '
					"If you're trying to add an emote using an image URL, "
					'you need to provide a name as the first argument, like this:\n'
					'`{}add NAME_HERE URL_HERE`'.format(context.prefix))
			else:
				animated, name, id = match.groups()
				url = self.db.emote_url(id, animated=animated)

		elif len(args) >= 2:
			name = args[0]
			match = self.RE_CUSTOM_EMOTE.match(args[1])
			if match is None:
				url = self.utils.strip_angle_brackets(args[1])
			else:
				url = self.db.emote_url(match.group('id'))

		elif not args:
			return await context.send('Your message had no emotes and no name!')

		async with context.typing():
			message = await self.add_safe(name, url, context.message.author.id)
		await context.send(message)

	async def add_safe(self, name, url, author_id):
		"""Try to add an emote. Returns a string that should be sent to the user."""
		try:
			emote = await self.add_backend(name, url, author_id)
		except discord.HTTPException as ex:
			logger.error(traceback.format_exc())
			return (
				'An error occurred while creating the emote:\n'
				+ self.utils.format_http_exception(ex))
		except asyncio.TimeoutError:
			return 'Error: retrieving the image took too long.'
		except ValueError:
			return 'Error: Invalid URL.'
		else:
			return f'Emote {emote} successfully created.'

	async def add_backend(self, name, url, author_id):
		"""Actually add an emote to the database."""
		await self.db.ensure_emote_does_not_exist(name)

		# credits to @Liara#0001 (ID 136900814408122368) for most of this part
		# https://gitlab.com/Pandentia/element-zero/blob/47bc8eeeecc7d353ec66e1ef5235adab98ca9635/element_zero/cogs/emoji.py#L217-228
		async with self.http.head(url, timeout=5) as response:
			if response.reason != 'OK':
				raise errors.HTTPException(response.status)
			if response.headers.get('Content-Type') not in ('image/png', 'image/jpeg', 'image/gif'):
				raise errors.InvalidImageError

		async with self.http.get(url) as response:
			if response.reason != 'OK':
				raise errors.HTTPException(response.status)
			image_data = BytesIO(await response.read())

		# resize_until_small is normally blocking, because wand is.
		# run_in_executor is magic that makes it non blocking somehow.
		# also, None as the executor arg means "use the loop's default executor"
		image_data = await self.bot.loop.run_in_executor(None, self.resize_until_small, image_data)
		animated = self.is_animated(image_data.getvalue())
		emote = await self.db.create_emote(name, author_id, animated, image_data.read())
		self.bot.dispatch('emote_add', emote)

		return emote

	@staticmethod
	def is_animated(image_data: bytes):
		"""Return whether the image data is animated, or raise InvalidImageError if it's not an image."""
		type = imghdr.what(None, image_data)
		if type == 'gif':
			return True
		elif type in ('png', 'jpeg'):
			return False
		else:
			raise errors.InvalidImageError

	@staticmethod
	def size(data: BytesIO):
		"""return the size, in bytes, of the data a BytesIO object represents"""
		old_pos = data.tell()
		data.seek(0, 2)  # seek to the end
		size = data.tell()
		data.seek(old_pos)  # put it back the way we found it
		return size

	@classmethod
	def resize_until_small(cls, image_data: BytesIO):
		"""If the image_data is bigger than 256KB, resize it until it's not"""
		# It's important that we only attempt to resize the image when we have to,
		# ie when it exceeds the Discord limit of 256KiB.
		# Apparently some <256KiB images become larger when we attempt to resize them,
		# so resizing sometimes does more harm than good.
		max_resolution = 128  # pixels
		size = cls.size(image_data)
		while size > 256 * 2**10 and max_resolution >= 32:  # don't resize past 32x32 or 256KiB
			logger.debug('image size too big (%s bytes)', size)
			logger.debug('attempting resize to %s*%s pixels', max_resolution, max_resolution)
			image_data = cls.thumbnail(image_data, (max_resolution, max_resolution))
			size = cls.size(image_data)
			max_resolution //= 2
		return image_data

	@classmethod
	def thumbnail(cls, image_data: BytesIO, max_size=(128, 128)):
		"""Resize an image in place to no more than max_size pixels, preserving aspect ratio."""
		# Credit to @Liara#0001 (ID 136900814408122368)
		# https://gitlab.com/Pandentia/element-zero/blob/47bc8eeeecc7d353ec66e1ef5235adab98ca9635/element_zero/cogs/emoji.py#L243-247
		image = Image(blob=image_data)
		image.resize(*cls.scale_resolution((image.width, image.height), max_size))
		# we create a new buffer here because there's wand errors otherwise.
		# specific error:
		# MissingDelegateError: no decode delegate for this image format `' @ error/blob.c/BlobToImage/353
		out = BytesIO()
		image.save(file=out)
		out.seek(0)
		return out

	@staticmethod
	def scale_resolution(old_res, new_res):
		# https://stackoverflow.com/a/6565988
		"""Resize a resolution, preserving aspect ratio. Returned w,h will be <= new_res"""
		old_width, old_height = old_res
		new_width, new_height = new_res
		old_ratio = old_width / old_height
		new_ratio = new_width / new_height
		if new_ratio > old_ratio:
			return (old_width * new_height//old_height, new_height)
		return new_width, old_height * new_width//old_width

	@commands.command(aliases=['delete', 'delet', 'del', 'rm'])
	async def remove(self, context, *names):
		"""Removes one or more emotes from the bot. You must own all of them."""
		if not names:
			return await context.send('Error: you must provide the name of at least one emote to remove')
		messages = []
		for name in names:
			try:
				emote = await self.db.get_emote(name)
			except errors.EmoteNotFoundError as ex:
				messages.append(str(ex))
				continue

			# log the emote removal *first* because if we were to do it afterwards,
			# the emote would not display (since it's already removed)
			removal_message = await self.logger.on_emote_remove(emote)
			try:
				await self.db.remove_emote(emote, context.author.id)
			except (errors.ConnoisseurError, errors.DiscordError) as ex:
				messages.append(str(ex))
				# undo the log
				await removal_message.delete()
			else:
				messages.append(f'`{emote} :{emote.name}:` was successfully deleted.')

		message = '\n'.join(messages)
		await context.send(self.utils.fix_first_line(message))

	@commands.command(aliases=['mv'])
	async def rename(self, context, *args):
		"""Renames an emote. You must own it.

		Example:
		ec/rename a b
		Renames :a: to :b:
		"""

		# allow e.g. foo{bar,baz} -> rename foobar to foobaz
		if len(args) == 1:
			print(utils.expand_cartesian_product(args[0]))
			old_name, new_name = utils.expand_cartesian_product(args[0])
			if not new_name:
				return await context.send('Error: you must provide a new name for the emote.')

		try:
			await self.db.rename_emote(old_name, new_name, context.author.id)
		except discord.HTTPException as ex:
			await context.send(self.utils.format_http_exception(ex))
		else:
			await context.send('Emote successfully renamed.')

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
		await context.try_add_reaction(self.utils.SUCCESS_EMOTES[True])

	@commands.command()
	@checks.not_blacklisted()
	async def react(self, context, emote: DatabaseEmote, *, message: HistoryMessage = None):
		"""Add a reaction to a message. Sad reacts only please.

		To specify the message, either provide a keyword to search for, or a message ID.
		If you don't specify a message, the last message sent in this channel will be chosen.
		Otherwise, the first message matching the keyword will be reacted to.
		"""

		sender_permissions = context.channel.permissions_for(context.author)
		permissions = context.channel.permissions_for(context.guild.me)
		if not sender_permissions.read_message_history or not permissions.read_message_history:
		    return await context.send('Unable to react: no permission to read message history.')
		if not sender_permissions.add_reactions or not permissions.add_reactions:
		    return await context.send('Unable to react: no permission to add reactions.')

		if message is None:
			# get the second to last message (ie ignore the invoking message)
			message = await self.utils.get_message(context.channel, -2)

		# there's no need to react to a message if that reaction already exists
		def same_emote(reaction):
			return getattr(reaction.emoji, 'id', None) == emote['id']

		if discord.utils.find(same_emote, message.reactions):
			return await context.send(
				'You can already react to that message with that emote.',
				delete_after=5)

		try:
			await message.add_reaction(emote.as_reaction())
		except discord.Forbidden:
			return await context.send('Unable to react: permission denied.')
		except discord.HTTPException:
			return await context.send('Unable to react. Discord must be acting up.')

		instruction_message = await context.send(
			"OK! I've reacted to that message. "
			"Please add your reaction now.")

		def check(payload):
			return (
				payload.message_id == message.id
				and payload.user_id == context.message.author.id
				and emote['id'] == getattr(payload.emoji, 'id', None))  # unicode emoji have no id

		try:
			await self.bot.wait_for('raw_reaction_add', timeout=30, check=check)
		except asyncio.TimeoutError:
			pass
		else:
			await self.db.log_emote_use(emote['id'])
		finally:
			# if we don't sleep, it would appear that the bot never un-reacted
			# i.e. the reaction button would still say "2" even after we remove our reaction
			# in my testing, 0.2s is the minimum amount of time needed to work around this.
			# unfortunately, if you look at the list of reactions, it still says the bot reacted.
			# no amount of sleeping can fix that, in my tests.
			await asyncio.sleep(0.2)
			await message.remove_reaction(emote.as_reaction(), context.guild.me)

			for message in context.message, instruction_message:
				try:
					await message.delete()
				except discord.HTTPException:
					pass

	@commands.command()
	async def list(self, context, *, user: discord.User = None):
		"""List all emotes the bot knows about.
		If a user is provided, the list will only contain emotes created by that user.
		"""

		await context.send('https://emoji-connoisseur.python-for.life/list' + (f'/{user.id}' if user else ''))

	@commands.command()
	async def popular(self, context):
		"""Lists popular emojis."""

		# code generously provided by @Liara#0001 under the MIT License:
		# https://gitlab.com/Pandentia/element-zero/blob/ca7d7f97e068e89334e66692922d9a8744e3e9be/element_zero/cogs/emoji.py#L364-399
		processed = []

		async with context.typing():
			async for i, emote in async_enumerate(self.db.popular_emotes()):
				if i == 200:
					break

				formatted = str(emote)

				author = self.utils.format_user(emote['author'], mention=True)

				c = emote['usage']
				multiple = '' if c == 1 else 's'

				processed.append(
					f'{formatted} (:{emote.name}:) '
					f'— used **{c}** time{multiple} '
					f'— owned by **{author}**')  # note: these are em dashes, not hyphens!

		paginator = ListPaginator(context, processed)
		self.paginators.add(paginator)
		await paginator.begin()

	@commands.command(name='steal-these', hidden=True)
	@checks.not_blacklisted()
	@utils.typing
	async def steal_these(self, context, *emotes):
		"""Steal a bunch of custom emotes."""
		if not emotes:
			return await context.send('You need to provide one or more custom emotes.')

		messages = []
		for match in self.RE_CUSTOM_EMOTE.finditer(''.join(emotes)):
			animated, name, id = match.groups()
			image_url = self.db.emote_url(id)
			messages.append(await self.add_safe(name, image_url, context.author.id))

		if not messages:
			return await context.send('Error: no existing custom emotes were provided.')

		message = '\n'.join(messages)
		await context.send(self.utils.fix_first_line(message))

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
			action = 'in to'
		else:
			action = 'out of'
		await context.send(f'Opted {action} the emote auto response.')

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
			new_state = 'opt-out'
		else:
			new_state = 'opt-in'
		await context.send(f'Emote auto response is now {new_state} for this server.')

	@commands.command()
	@commands.is_owner()
	async def blacklist(self, context, user: discord.Member, *, reason=None):
		"""Prevent a user from using commands and the emote auto response.
		If you don't provide a reason, the user will be un-blacklisted."""
		await self.db.set_user_blacklist(user.id, reason)
		if reason is None:
			await context.send('User un-blacklisted.')
		else:
			await context.send(f'User blacklisted with reason `{reason}`.')

	@commands.command(hidden=True)
	@commands.is_owner()
	async def preserve(self, context, should_preserve: bool, *names):
		"""Sets preservation status of emotes."""
		names = set(names)
		for name in names:
			try:
				emote = await self.db.set_emote_preservation(name, should_preserve)
			except errors.EmoteNotFoundError as ex:
				await context.send(ex)
			else:
				self.bot.dispatch(f'emote_{"un" if not should_preserve else ""}preserve', emote)
		await context.send(self.utils.SUCCESS_EMOTES[True])

	## EVENTS

	async def on_command_error(self, context, error):
		if isinstance(error, errors.ConnoisseurError):
			await context.send(error)

	async def on_message(self, message):
		"""Reply to messages containing :name: or ;name; with the corresponding emotes.
		This is like half the functionality of the bot"""
		if not self.bot.should_reply(message):
			return

		await self.db.ready.wait()

		context = await self.bot.get_context(message)
		if context.valid:
			# user invoked a command, rather than the emote auto response
			# so don't a second time
			return

		if message.guild and not message.guild.me.permissions_in(message.channel).external_emojis:
			return

		if message.guild:
			guild = message.guild.id
		else:
			guild = None

		if not await self.db.get_state(guild, message.author.id):
			return

		blacklist_reason = await self.db.get_user_blacklist(message.author.id)
		if blacklist_reason is not None:
			try:
				await message.author.send(
					f'You have been blacklisted from using emotes with the reason `{blacklist_reason}`. '
					'To appeal, please join the support server using the support command.')
			except discord.HTTPException:
				pass
			return

		reply = await self.extract_emotes(message.content)
		if reply is None:  # don't send empty whitespace
			return

		self.replies[message.id] = await message.channel.send(reply)

	async def on_raw_message_edit(self, payload):
		"""Ensure that when a message containing emotes is edited, the corresponding emote reply is, too."""
		# data = https://discordapp.com/developers/docs/resources/channel#message-object
		if payload.message_id not in self.replies or 'content' not in payload.data:
			return

		emotes = await self.extract_emotes(payload.data['content'], log_usage=False)
		reply = self.replies[payload.message_id]
		if emotes is None:
			del self.replies[payload.message_id]
			return await reply.delete()
		elif emotes == reply.content:
			# don't edit a message if we don't need to
			return

		await reply.edit(content=emotes)

	async def extract_emotes(self, message: str, *, log_usage=True):
		"""Parse all emotes (:name: or ;name;) from a message"""
		# don't respond to code blocks or custom emotes, since custom emotes also have :foo: in them
		message = self.RE_CODE.sub('', message)
		message = self.RE_CUSTOM_EMOTE.sub('', message)

		extracted = []
		emotes_used = set()
		for match in self.RE_EMOTE.finditer(message):
			name, newline = match.groups()[1:]  # the first group matches : or ;
			if name:
				try:
					db_emote = await self.db.get_emote(name)
				except errors.EmoteNotFoundError:
					continue
				else:
					extracted.append(str(db_emote))
					emotes_used.add(db_emote.id)
			if newline:
				extracted.append(newline)

		if log_usage:
			for emote in emotes_used:
				await self.db.log_emote_use(emote)

		# remove leading and trailing newlines
		# e.g. if someone sends
		# foo
		# bar
		# :cruz:
		# :cruz:
		#
		# quux, we should only send :cruz:\n:cruz:
		extracted = ''.join(extracted).strip()
		if extracted:
			return self.utils.fix_first_line(extracted)

	async def delete_reply(self, message_id):
		"""Delete our reply to a message containing emotes."""
		try:
			message = self.replies.pop(message_id)
		except KeyError:
			return

		try:
			await message.delete()
		except discord.HTTPException:
			pass

	async def on_raw_message_delete(self, payload):
		"""Ensure that when a message containing emotes is deleted, the emote reply is, too."""
		await self.delete_reply(payload.message_id)

	async def on_raw_bulk_message_delete(self, payload):
		for message_id in payload.message_ids:
			await self.delete_reply(message_id)


def setup(bot):
	bot.add_cog(Emotes(bot))
