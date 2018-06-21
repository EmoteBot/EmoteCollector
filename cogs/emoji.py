#!/usr/bin/env python3.6
# encoding: utf-8

import asyncio
import imghdr
from io import BytesIO, StringIO
import itertools
import logging
import re
import traceback

import aiohttp
import asyncpg
from bs4 import BeautifulSoup
import discord
from discord.ext import commands
from wand.image import Image

import utils
from utils import async_enumerate
from utils import checks
from utils import errors
from utils.paginator import ListPaginator

logger = logging.getLogger('cogs.emoji')


class Emotes:
	"""Commands related to the main functionality of the bot"""

	"""Matches :foo: and ;foo; but not :foo;. Used for emotes in text."""
	RE_EMOTE = re.compile(r'(:|;)(\w{2,32})\1', re.ASCII)

	"""Matches only custom server emoji."""
	RE_CUSTOM_EMOTE = re.compile(r'<a?:(\w{2,32}):(\d{15,21})>', re.ASCII)

	"""Matches code blocks, which should be ignored."""
	RE_CODE = re.compile(r'(`{1,3}).+?\1', re.DOTALL)

	def __init__(self, bot):
		self.bot = bot
		self.utils = self.bot.get_cog('Utils')
		self.db = self.bot.get_cog('Database')
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

	def __unload(self):
		# aiohttp can't decide if this should be a coroutine...
		# i think it shouldn't be, since it never awaits
		self.bot.loop.create_task(self.http.close())

	## COMMANDS

	@commands.command()
	@checks.not_blacklisted()
	async def info(self, context, name):
		"""Gives info on an emote.

		- name: the name of the emote to get info on
		"""
		await self.db.ensure_emote_exists(name)
		emote = await self.db.get_emote(name)

		embed = discord.Embed()

		title = self.db.format_emote(emote)
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
		message = [
			f'Static emotes: {static}',
			f'Animated emotes: {animated}',
			f'Total: {total}']
		await context.send(self.utils.fix_first_line(message))

	@commands.command()
	@checks.not_blacklisted()
	async def big(self, context, name):
		"""Shows the original image for the given emote"""
		await self.db.ensure_emote_exists(name)
		emote = await self.db.get_emote(name)

		embed = discord.Embed(title=emote['name'])
		embed.set_image(url=self.db.emote_url(emote['id'], emote['animated']))
		await context.send(embed=embed)

	@commands.command(aliases=['create'])
	@checks.not_blacklisted()
	@utils.typing
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
				return await context.send("That's not a custom emote.")
			else:
				name, id = match.groups()
				url = self.db.emote_url(id)

		elif len(args) == 2:
			name = args[0]
			match = self.RE_CUSTOM_EMOTE.match(args[1])
			if match is None:
				url = self.utils.strip_angle_brackets(args[1])
			else:
				url = self.db.emote_url(match.group(2))

		else:
			return await context.send('Your message had no emotes and no name!')

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
				+ self.format_http_exception(ex))
		except asyncio.TimeoutError:
			return 'Error: retrieving the image took too long.'
		except ValueError:
			return 'Error: Invalid URL.'
		else:
			return f'Emote {self.db.format_emote(emote)} successfully created.'

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
	@utils.typing
	async def remove(self, context, *args):
		"""Removes one or more emotes from the bot. You must own all of them."""
		messages = []
		for name in args:
			try:
				await self.db.owner_check(name, context.author.id)
			except errors.ConnoisseurError as ex:
				messages.append(str(ex))
				continue
			db_emote = await self.db.get_emote(name)
			logger.debug('Trying to delete %s %s', db_emote['name'], db_emote['id'])

			try:
				await self.db.remove_emote(name, context.author.id)
			except (errors.ConnoisseurError, errors.DiscordError) as ex:
				messages.append(str(ex))

			messages.append(f'`:{db_emote["name"]}:` was successfully deleted.')

		await context.send(self.utils.fix_first_line(messages))

	@commands.command(aliases=['mv'])
	async def rename(self, context, old_name, new_name):
		"""Renames an emote. You must own it."""
		try:
			await self.db.rename_emote(old_name, new_name, context.author.id)
		except discord.HTTPException as ex:
			await context.send(self.format_http_exception(ex))
			logger.error('Rename:')
			logger.error(traceback.format_exc())
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

	@staticmethod
	def format_http_exception(exception: discord.HTTPException):
		"""Formats a discord.HTTPException for relaying to the user.
		Sample return value:

		BAD REQUEST (status code: 400):
		Invalid Form Body
		In image: File cannot be larger than 256 kb.
		"""
		return f'{exception.response.reason} (status code: {exception.response.status}):\n{exception.text}'

	@commands.command()
	@checks.not_blacklisted()
	async def react(self, context, name, message: int = None, channel: discord.TextChannel = None):
		"""Add a reaction to a message. Sad reacts only please.
		If no message ID and no channel is provided, it'll react to the last sent message.
		You can get the message ID by enabling developer mode (in Settings→Appearance),
		then right clicking on the message you want and clicking "Copy ID".
		"""
		await self.db.ensure_emote_exists(name)
		db_emote = await self.db.get_emote(name)

		if channel is None:
			channel = context.channel

		if message is None:
			# get the second to last message (ie ignore the invoking message)
			message = await self.utils.get_message(context.channel, -2)
		else:
			try:
				message = await channel.get_message(message)
			except discord.NotFound:
				return await context.send(
					'Message not found! Make sure your message and channel IDs are correct.')
			except discord.Forbidden:
				return await context.send(
					'Permission denied! Make sure the bot has permission to read that message.')

		# there's no need to react to a message if that reaction already exists
		def same_emote(reaction):
			return getattr(reaction.emoji, 'id', None) == db_emote['id']

		if discord.utils.find(same_emote, message.reactions):
			return await context.send('You can already react to that message, silly!', delete_after=5)

		emote_str = self.utils.strip_angle_brackets(self.db.format_emote(db_emote))

		await context.try_add_reaction(
			emote_str,
			message,
			'Permission denied! Make sure the bot has permission to react to that message.')

		def check(payload):
			return (
				payload.message_id == message.id
				and payload.user_id == context.message.author.id
				and db_emote['id'] == getattr(payload.emoji, 'id', None))  # unicode emoji have no id

		try:
			await self.bot.wait_for('raw_reaction_add', timeout=30, check=check)
		except asyncio.TimeoutError:
			logger.warn("react: user didn't react in time")
		else:
			await self.db.log_emote_use(db_emote['id'])
		finally:
			# if we don't sleep, it would appear that the bot never un-reacted
			# i.e. the reaction button would still say "2" even after we remove our reaction
			# in my testing, 0.2s is the minimum amount of time needed to work around this.
			# unfortunately, if you look at the list of reactions, it still says the bot reacted.
			# no amount of sleeping can fix that, in my tests.
			await asyncio.sleep(0.2)
			await message.remove_reaction(emote_str, context.guild.me)
			try:
				await context.message.delete()
			except discord.errors.HTTPException:
				# we're not allowed to delete the invoking message, or the user already has
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
		await context.trigger_typing()

		processed = []

		async for i, emote in async_enumerate(self.db.get_popular_emotes()):
			if i == 200:
				break

			formatted = self.db.format_emote(emote)

			author = self.utils.format_user(emote['author'], mention=True)

			c = emote['usage']
			multiple = '' if c == 1 else 's'

			processed.append(f'{formatted}, used **{c}** time{multiple}, owned by **{author}**')

		paginator = ListPaginator(context, processed)
		await paginator.begin()

	@commands.command(name='recover-db', hidden=True)
	@commands.is_owner()
	@utils.typing
	async def recover_db(self, context, list_url):
		emotes = await self.scrape_list(list_url)

		for name, url, author in emotes:
			id, animated = self.utils.emote_info(url)
			await self.db.db.execute("""
					INSERT INTO emojis(name, id, author, animated)
					VALUES($1,$2,$3,$4)""",
				name, id, author, animated)

		await context.try_add_reaction(self.utils.SUCCESS_EMOTES[True])

	@commands.command(name='steal-all', hidden=True)
	@commands.is_owner()
	@utils.typing
	async def steal_all(self, context, list_url):
		"""Steal all emotes listed on a markdown file given by the list_url.
		This file must have the same format as the one generated by the ec/list command.
		"""
		emotes = await self.scrape_list(list_url)

		for name, image, author in emotes:
			messages = []
			message = await self.add_safe(name, image, author)
			if message is None:
				logger.warn('add_safe returned None')
			else:
				messages.append(message)
		await context.send('\n'.join(messages))

	async def scrape_list(self, list_url):
		"""Extract all emotes from a given list URL, in the format produced by ec/add.
		Return an iterable of (name, image, author ID) tuples."""

		try:
			async with self.http.get(list_url) as resp:
				text = await resp.text()
		except asyncio.TimeoutError:
			raise errors.ConnoisseurError('Error: fetching the URL took too long.')
		except ValueError:
			raise errors.ConnoisseurError('Error: invalid URL.')

		return self.parse_list(text)

	@staticmethod
	def parse_list(text):
		"""Parse an emote list retrieved from ec/add."""

		rows = [line.split(' | ') for line in text.splitlines()[2:]]
		image_column = (row[0] for row in rows)
		soup = BeautifulSoup(''.join(image_column), 'lxml')
		images = soup.find_all(name='a')
		image_urls = [image.get('href') for image in images]
		names = [row[1].replace('`', '').replace(':', '') for row in rows if len(row) > 1]
		# example: @null byte#8191 (140516693242937345)
		# this gets just the ID
		authors = [
			int(row[2].split()[-1].replace('(', '').replace(')', ''))
			for row in rows
			if len(row) > 2]

		return zip(names, image_urls, authors)

	@commands.command(name='steal-these', hidden=True)
	@checks.not_blacklisted()
	@utils.typing
	async def steal_these(self, context, *emotes):
		"""Steal a bunch of custom emotes."""
		if not emotes:
			return await context.send('You need to provide one or more custom emotes.')

		messages = []
		for match in self.RE_CUSTOM_EMOTE.finditer(''.join(emotes)):
			name, id = match.groups()
			image_url = self.db.emote_url(id)
			messages.append(await self.add_safe(name, image_url, context.author.id))
		# XXX this will fail if len > 2000
		await context.send(self.utils.fix_first_line(messages))

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
				await self.db.set_emote_preservation(name, should_preserve)
			except errors.EmoteNotFoundError as ex:
				await context.send(ex)
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
		if message.guild and not message.guild.me.permissions_in(message.channel).external_emojis:
			return

		if isinstance(message.channel, discord.DMChannel):
			guild = None
		else:
			guild = message.guild.id

		if not await self.db.get_state(guild, message.author.id):
			return

		reply = await self.extract_emotes(message.content)
		if reply is None:  # don't send empty whitespace
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
		lines = message.splitlines()

		extracted_lines = []
		emotes_used = set()
		for line in lines:
			extracted_line, emotes_used_line = await self.extract_emotes_line(line)
			extracted_lines.append(extracted_line)
			emotes_used.update(emotes_used_line)

		if log_usage:
			for emote in emotes_used:
				await self.db.log_emote_use(emote)

		# remove leading newlines
		# e.g. if someone sends
		# foo
		# bar
		# :cruz:
		# :cruz:
		#
		# quux, we should only send :cruz:\n:cruz:
		extracted_lines = itertools.dropwhile(lambda line: not line, extracted_lines)
		# remove trailing newlines
		extracted_lines = itertools.takewhile(bool, extracted_lines)

		result_message = self.utils.fix_first_line(list(extracted_lines))
		if result_message.replace('\N{zero width space}', '').strip() != '':  # don't send an empty message
			return result_message

	async def extract_emotes_line(self, line: str) -> str:
		"""Extract emotes from a single line."""
		# RE_EMOTE uses the first group to match the same punctuation mark on both ends,
		# so the second group is the actual name
		names = [match.group(2) for match in self.RE_EMOTE.finditer(line)]
		if not names:
			return '', set()

		formatted_emotes = []
		emotes_used = set()
		for name in names:
			emote = await self.db.get_emote(name)
			if emote is None:
				continue
			formatted_emotes.append(self.db.format_emote(emote))
			emotes_used.add(emote['id'])

		return ''.join(formatted_emotes), emotes_used

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
