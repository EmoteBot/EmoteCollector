#!/usr/bin/env python3.6
# encoding: utf-8

import asyncio
import imghdr
from io import BytesIO, StringIO
import logging
import random
import re
import traceback

import aiohttp
import asyncpg
from bs4 import BeautifulSoup
import discord
from discord.ext import commands
from wand.image import Image

import utils
from utils import checks
from utils import errors

logger = logging.getLogger('cogs.emoji')


class Emotes:
	"""Commands related to the main functionality of the bot"""

	"""Matches :foo: and ;foo; but not :foo;. Used for emotes in text."""
	RE_EMOTE = re.compile(r'(:|;)(\w{2,32})\1', re.ASCII)

	"""Matches only custom server emoji."""
	RE_CUSTOM_EMOTE = re.compile(r'<a?:(\w{2,32}):(\d{15,21})>', re.ASCII)

	"""Matches code blocks, which should be ignored."""
	RE_CODE = re.compile(r'`{1,3}.+?`{1,3}', re.DOTALL)

	def __init__(self, bot):
		self.bot = bot
		self.utils = self.bot.get_cog('Utils')
		self.db = self.bot.get_cog('Database')
		self.session = aiohttp.ClientSession(loop=self.bot.loop, read_timeout=30)

		# Keep track of replies so that if the user edits/deletes a message,
		# we delete/edit the corresponding reply.
		# Don't store too many of these replies.
		# TODO investigate how much RAM this dict actually uses. (sys.getsizeof)
		self.replies = utils.LRUDict(size=1000)

	def __unload(self):
		self.session.close()

	## COMMANDS

	@commands.command()
	@checks.not_blacklisted()
	async def info(self, context, name):
		"""Gives info on an emote.

		- name: the name of the emote to get info on
		"""
		await self.db.ensure_emote_exists(name)
		emote = await self.db.get_emote(name)

		embed = discord.Embed(title=self.db.format_emote(emote))
		if emote['created'] is not None:
			logger.debug('setting timestamp to %s', emote['created'])
			embed.timestamp = emote['created']
			embed.set_footer(text='Created')

		embed.add_field(
			name='Owner',
			# prevent modified and owner from being jammed up against each other
			# #BlameDiscord™
			value=self.utils.format_user(emote['author'], mention=True) + '\N{hangul filler}')
		if emote['modified'] is not None:
			embed.add_field(
				name='Modified',
				value=self.utils.format_time(emote['modified']))
		if emote['description'] is not None:
			embed.add_field(name='Description', value=emote['description'], inline=False)

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

		async with self.session.get(self.db.emote_url(emote['id'])) as resp:
			extension = '.gif' if emote['animated'] else '.png'
			await context.send(file=discord.File(BytesIO(await resp.read()), emote['name'] + extension))

	@commands.command(aliases=['create'])
	@checks.not_blacklisted()
	@utils.typing
	async def add(self, context, *args):
		"""Add a new emote to the bot. You can use it like this:
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
				return await context.send("That's not an emote!")
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
		if message is None:
			logger.warn('add_safe returned None')
		else:
			await context.send(message)

	async def add_safe(self, name, url, author):
		"""Try to add an emote. Returns a string that should be sent to the user."""
		try:
			await self.add_backend(name, url, author)
		except errors.HTTPException as ex:
			return f'URL error: server returned error code {ex}.'
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
			# f-strings are not async so we use % formatting instead
			return 'Emote %s successfully created.' % await self.db.get_formatted_emote(name)

	async def add_backend(self, name, url, author_id):
		"""Actually add an emote to the database."""
		await self.db.ensure_emote_does_not_exist(name)

		# credits to @Liara#0001 (ID 136900814408122368) for most of this part
		# https://gitlab.com/Pandentia/element-zero/blob/47bc8eeeecc7d353ec66e1ef5235adab98ca9635/element_zero/cogs/emoji.py#L217-228
		async with self.session.head(url, timeout=5) as response:
			if response.reason != 'OK':
				raise errors.HTTPException(response.status)
			if response.headers.get('Content-Type') not in ('image/png', 'image/jpeg', 'image/gif'):
				raise errors.InvalidImageError

		async with self.session.get(url) as response:
			if response.reason != 'OK':
				raise errors.HTTPException(response.status)
			image_data = BytesIO(await response.read())

		image_data = await self.bot.loop.run_in_executor(None, self.resize_until_small, image_data)
		animated = self.is_animated(image_data.getvalue())
		emote = await self.db.create_emote(name, author_id, animated, image_data.read())

	@staticmethod
	def is_animated(image_data: bytes):
		"""Return if the image data is animated, or raise InvalidImageError if it's not an image."""
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
		# ie when it exceeds the Discord limit of 256KB.
		# Apparently some <256KB images become larger when we attempt to resize them,
		# so resizing sometimes does more harm than good.
		max_resolution = 128  # pixels
		size = cls.size(image_data)
		while size > 256_000 and max_resolution > 16:  # don't resize past 32x32
			logger.debug('image size too big (%s bytes)', size)
			logger.debug('attempting resize to %s*%s pixels', max_resolution, max_resolution)
			# resize_image is normally blocking, because wand is.
			# run_in_executor is magic that makes it non blocking somehow.
			# also, None as the executor arg means "use the loop's default executor"
			image_data = cls.thumbnail(image_data, (max_resolution, max_resolution))
			size = cls.size(image_data)
			max_resolution //= 2
		return image_data

	@classmethod
	def thumbnail(cls, image_data: BytesIO, max_size=(128, 128)):
		"""Resize an image to no more than max_size pixels, preserving aspect ratio."""
		# Credit to @Liara#0001 (ID 136900814408122368)
		# https://gitlab.com/Pandentia/element-zero/blob/47bc8eeeecc7d353ec66e1ef5235adab98ca9635/element_zero/cogs/emoji.py#L243-247
		image = Image(blob=image_data)
		image.resize(*cls.scale_resolution((image.width, image.height), max_size))
		# TODO investigate whether we can mutate the original arg or if we have to create a new buffer
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
		try:
			await self.db.set_emote_description(name, context.author.id, description)
		except errors.ConnoisseurError as ex:
			await context.send(ex)

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
	async def react(self, context, name, message: int = None, channel: int = None):
		"""Add a reaction to a message. Sad reacts only please.
		If no message ID and no channel ID is provided, it'll react to the last sent message.
		You can get the message ID by enabling developer mode (in Settings→Appearance),
		then right clicking on the message you want and clicking "Copy ID". Same for channel IDs.
		"""
		await self.db.ensure_emote_exists(name)
		db_emote = await self.db.get_emote(name)

		if channel is None:
			channel = context.channel
		else:
			channel = context.guild.get_channel(channel)

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

		def check(emote, message_id, channel_id, user_id):
			return (
				message_id == message.id
				and user_id == context.message.author.id
				and db_emote['id'] == getattr(emote, 'id', None))  # unicode emoji have no id

		try:
			await self.bot.wait_for('raw_reaction_add', timeout=30, check=check)
		except asyncio.TimeoutError:
			logger.warn("react: user didn't react in time")
		finally:
			await asyncio.sleep(0.6)
			await message.remove_reaction(emote_str, context.guild.me)
			try:
				await context.message.delete()
			except discord.errors.Forbidden:
				pass

	@commands.command()
	@checks.not_blacklisted()
	@utils.typing
	async def list(self, context, *, user: discord.User = None):
		"""List all emotes the bot knows about.
		If a user is provided, the list will only contain emotes created by that user.
		"""

		table = StringIO()
		table.write('Emoji | Name | Author\n')
		table.write('----- | ---- | ------\n')

		async for row in self.db.get_emotes(None if user is None else user.id):
			table.write(self.format_row(row) + '\n')

		description = 'list of all emotes'
		if user is not None:
				# e.g. "list of all emotes by null_byte#8191 (140516693242937345)"
				description += ' by ' + self.utils.format_user(user.id, mention=False)

		gist_url = await self.utils.create_gist('list.md', table.getvalue(), description=description)
		await context.send(f'<{gist_url}>')

	def format_row(self, record: asyncpg.Record):
		"""Format a database record as "markdown" for the ec/list command."""
		name, id, author, *_ = record  # discard extra columns
		author = self.utils.format_user(author)
		url = self.db.emote_url(id)
		# only set the width in order to preserve the aspect ratio of the emote
		# however, if someone makes a really tall image this will still break that.
		return f'<a href="url"><img src="{url}" width=32px></a> | `:{name}:` | {author}'

	@commands.command(name='steal-all', hidden=True)
	@commands.is_owner()
	@utils.typing
	async def steal_all(self, context, list_url):
		"""Steal all emotes listed on a markdown file given by the list_url.
		This file must have the same format as the one generated by Element Zero's e0list command.
		"""
		try:
			emotes = await self.scrape_list(list_url)
		except asyncio.TimeoutError:
			return await context.send('Error: fetching the URL took too long.')
		except ValueError as ex:
			logging.warning('steal_all: %s %s', type(ex).__name__, ex)
			return await context.send('Error: invalid URL.')

		for name, image, author in emotes:
			messages = []
			message = await self.add_safe(name, image, author)
			if message is None:
				logger.warn('add_safe returned None')
			else:
				messages.append(message)
		await context.send('\n'.join(messages))

	async def scrape_list(self, list_url):
		"""Extract all emotes from a given list URL, in Element Zero's format.
		Return an iterable of (name, image, author ID) tuples."""
		async with self.session.get(list_url) as resp:
			text = await resp.text()
		return self.parse_list(text)

	def parse_list(self, text):
		"""Parse an emote list retrieved from Element Zero."""

		rows = [line.split(' | ') for line in text.split('\n')[2:]]
		image_column = (row[0] for row in rows)
		soup = BeautifulSoup(''.join(image_column), 'lxml')
		images = soup.find_all(attrs={'class': 'emoji'})
		image_urls = [image.get('src') for image in images]
		names = [row[1].replace('`', '').replace(':', '') for row in rows if len(row) > 1]
		# example: @null byte#8191 (140516693242937345)
		# this gets just the ID
		authors = [int(row[2].split()[-1].replace('(', '').replace(')', '')) for row in rows if len(row) > 2]

		return zip(names, image_urls, authors)

	@commands.command(name='steal-these')
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

		Opt out mode is useful for very large servers where the bot's response would be annoying or
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

	## EVENTS

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
			except (discord.HTTPException, discord.Forbidden):
				pass
			return

		self.replies[message.id] = await message.channel.send(reply)

	async def on_raw_message_edit(self, message_id, data):
		"""Ensure that when a message containing emotes is edited, the corresponding emote reply is, too."""
		# data = https://discordapp.com/developers/docs/resources/channel#message-object
		if message_id not in self.replies or 'content' not in data:
			return

		emotes = await self.extract_emotes(data['content'])
		reply = self.replies[message_id]
		if emotes is None:
			del self.replies[message_id]
			return await reply.delete()
		elif emotes == reply.content:
			# don't edit a message if we don't need to
			return

		await reply.edit(content=emotes)

	async def extract_emotes(self, message: str):
		"""Parse all emotes (:name: or ;name;) from a message"""
		# don't respond to code blocks or custom emotes, since custom emotes also have :foo: in them
		message = self.RE_CODE.sub('', message)
		message = self.RE_CUSTOM_EMOTE.sub('', message)
		lines = message.splitlines()

		result = [await self.extract_emotes_line(line) for line in lines]
		result_message = self.utils.fix_first_line(result)

		if result_message.replace('\N{zero width space}', '').strip() != '':  # don't send an empty message
			return result_message

	async def extract_emotes_line(self, line: str) -> str:
		"""Extract emotes from a single line."""
		# RE_EMOTE uses the first group to match the same punctuation mark on both ends,
		# so the second group is the actual name
		names = [match.group(2) for match in self.RE_EMOTE.finditer(line)]
		if not names:
			return ''

		formatted_emotes = []
		for name in names:
			emote = await self.db.get_emote(name)
			if emote is None:
				continue
			formatted_emotes.append(self.db.format_emote(emote))

		return ''.join(formatted_emotes)

	async def on_raw_message_delete(self, message_id, _):
		"""Ensure that when a message containing emotes is deleted, the emote reply is, too."""
		try:
			message = self.replies.pop(message_id)
		except KeyError:
			return

		try:
			await message.delete()
		except discord.HTTPException:
			pass

	async def on_raw_bulk_message_delete(self, message_ids, _):
		for message_id in message_ids:
			await self.on_raw_message_delete(message_id, _)


class BackendContext(utils.CustomContext):
	async def fail_if_not_owner(self, name):
		# It may seem bad to do two identical database queries like this,
		# but I'm pretty sure asyncpg caches queries.
		await self.cog.db.ensure_emote_exists(name)
		await self.cog.db.owner_check(name, self.author.id)


def setup(bot):
	bot.add_cog(Emotes(bot))
