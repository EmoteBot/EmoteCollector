#!/usr/bin/env python3
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
		self.bot.loop.create_task(self.find_backend_guilds())
		self.utils = self.bot.get_cog('Utils')
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
	async def support(self, context):
		"""Directs you the support server."""
		try:
			await context.author.send('https://discord.gg/' + self.bot.config['support_server_invite_code'])
			await context.try_add_reaction('\N{ok hand sign}')
		except discord.HTTPException:
			await context.try_add_reaction('\N{cross mark}')
			await context.send('Unable to send invite in DMs. Please allow DMs from server members.')

	@commands.command()
	async def info(self, context, name):
		"""Gives info on an emote.

		- name: the name of the emote to get info on
		"""
		await context.fail_if_not_exists(name)
		emote = await self.get(name)

		embed = discord.Embed(title=self.utils.format_emote(emote))
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
			embed.add_field(name='Description',  value=emote['description'], inline=False)

		await context.send(embed=embed)

	@commands.command()
	async def big(self, context, name):
		"""Shows the original image for the given emote"""
		await context.fail_if_not_exists(name)
		emote = await self.get(name)

		async with self.session.get(self.utils.emote_url(emote['id'])) as resp:
			extension = '.gif' if emote['animated'] else '.png'
			await context.send(file=discord.File(BytesIO(await resp.read()), emote['name'] + extension))

	@commands.command(aliases=['create'])
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
				url = self.utils.emote_url(id)

		elif len(args) == 2:
			name = args[0]
			match = self.RE_CUSTOM_EMOTE.match(args[1])
			if match is None:
				url = self.utils.strip_angle_brackets(args[1])
			else:
				url = self.utils.emote_url(match.group(2))

		else:
			return await context.send('Your message had no emotes and no name!')

		message = await self.add_safe(name, url, context.message.author.id)
		if message is None:
			logger.warn('add_safe returned None')
		else:
			await context.send(message)

	async def add_safe(self, name, url, author):
		"""Try to add an emote. On failure, return a string that should be sent to the user."""
		try:
			await self.add_backend(name, url, author)
		except EmoteExistsError:
			return f'An emote called {name} already exists!'
		except discord.HTTPException as ex:
			logger.error(traceback.format_exc())
			return (
				'An error occurred while creating the emote:\n'
				+ self.format_http_exception(ex))
		except HTTPException as ex:
			return f'URL error: server returned error code {ex}.'
		except asyncio.TimeoutError:
			return 'Error: retrieving the image took too long.'
		except InvalidImageError:
			return 'Error: URL specified is not a PNG, JPG, or GIF.'
		except ValueError:
			return 'Error: Invalid URL.'
		else:
			return 'Emote %s successfully created.' % await self.get_formatted(name)

	async def add_backend(self, name, url, author_id):
		"""Actually add an emote to the database."""
		if await self.exists(name):
			raise EmoteExistsError(name)

		# after reaching this point, the emote doesn't exist already

		# credits to @Liara#0001 (ID 136900814408122368) for most of this part
		# https://gitlab.com/Pandentia/element-zero/blob/47bc8eeeecc7d353ec66e1ef5235adab98ca9635/element_zero/cogs/emoji.py#L217-228
		async with self.session.head(url, timeout=5) as response:
			if response.reason != 'OK':
				raise HTTPException(response.status)
			if response.headers.get('Content-Type') not in ('image/png', 'image/jpeg', 'image/gif'):
				raise InvalidImageError

		async with self.session.get(url) as response:
			if response.reason != 'OK':
				raise HTTPException(response.status)
			image_data = BytesIO(await response.read())

		image_data = await self.bot.loop.run_in_executor(None, self.resize_until_small, image_data)

		animated = self.is_animated(image_data.getvalue())
		guild = self.free_guild(animated)
		emote = await guild.create_custom_emoji(name=name, image=image_data.read())
		await self.bot.db.execute(
			'INSERT INTO emojis(name, id, author, animated) VALUES($1, $2, $3, $4)',
			name,
			emote.id,
			author_id,
			animated)

	@staticmethod
	def is_animated(image_data: bytes):
		"""Return if the image data is animated, or raise InvalidImageError if it's not an image."""
		type = imghdr.what(None, image_data)
		if type == 'gif':
			return True
		elif type in ('png', 'jpeg'):
			return False
		else:
			raise InvalidImageError

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
			await context.fail_on_bad_emote(name)
			db_emote = await self.get(name)
			logger.debug('Trying to delete %s %s', db_emote['name'], db_emote['id'])

			emote = self.bot.get_emoji(db_emote['id'])
			if emote is None:
				return await context.send('Discord seems to be having issues right now, try again later.')

			await self.bot.db.execute('DELETE FROM emojis WHERE name ILIKE $1', name)
			await emote.delete()
			messages.append(f'`:{db_emote["name"]}:` was successfully deleted.')

		await context.send(self.utils.fix_first_line(messages))

	@commands.command(aliases=['mv'])
	async def rename(self, context, old_name, new_name):
		"""Renames an emote. You must own it."""
		await context.fail_on_bad_emote(old_name)
		if await self.exists(new_name):
			return await context.send(f'{new_name} already exists!')
		emote = await self.get(old_name)

		try:
			await self.rename_backend(emote['id'], new_name)
		except discord.Forbidden:
			await context.send(
				'Unable to rename the emote because of missing permissions. This should not happen.\n'
				'Please contact @null byte#8191.')
			logger.error('Missing permissions to rename ' + old_name)
			logger.error(traceback.format_exc())
		except discord.HTTPException as exception:
			await context.send(self.format_http_exception(exception))
			logger.error('Rename:')
			logger.error(traceback.format_exc())
		else:
			await context.send('Emote successfully renamed.')

	async def rename_backend(self, id, new_name):
		emote = self.bot.get_emoji(id)
		await emote.edit(name=new_name)
		await self.bot.db.execute('UPDATE emojis SET name = $2 WHERE id = $1', id, new_name)

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
	async def react(self, context, name, message: int = None, channel: int = None):
		"""Add a reaction to a message. Sad reacts only please.
		If no message ID and no channel ID is provided, it'll react to the last sent message.
		You can get the message ID by enabling developer mode (in Settings→Appearance),
		then right clicking on the message you want and clicking "Copy ID". Same for channel IDs.
		"""
		await context.fail_if_not_exists(name)
		db_emote = await self.get(name)

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

		emote_str = self.utils.strip_angle_brackets(self.utils.format_emote(db_emote))

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

			success = False
			error_message = "Error: description too long! It's an emote, not your life story."
		else:
			success = True
			error_message = ''

		await context.try_add_reaction(self.utils.SUCCESS_EMOTES[success], fallback_message=error_message)

	@commands.command()
	@utils.typing
	async def list(self, context, *, user: discord.User = None):
		"""List all emotes the bot knows about.
		If a user is provided, the list will only contain emotes created by that user.
		"""

		table = StringIO()
		table.write('Emoji | Name | Author\n')
		table.write('----- | ---- | ------\n')

		query = 'SELECT * FROM emojis '
		args = []
		if user is not None:
			query += 'WHERE author = $1 '
			args.append(user.id)
		query += 'ORDER BY LOWER(name)'

		# gee whiz, look at all these indents!
		async with self.bot.db.acquire() as connection:
			async with connection.transaction():
				async for row in connection.cursor(query, *args):
					table.write(self.format_row(row) + '\n')

		description = 'list of all emotes'
		if user is not None:
			# e.g. 'list of all emotes by null_byte#8191 (140516693242937345)
			description += ' by ' + self.utils.format_user(user.id, mention=False)
		gist_url = await self.utils.create_gist('list.md', table.getvalue(), description=description)
		await context.send(f'<{gist_url}>')

	def format_row(self, record: asyncpg.Record):
		"""Format a database record as "markdown" for the ec/list command."""
		name, id, author, *_ = record  # discard extra columns
		author = self.utils.format_user(author)
		# only set the width in order to preserve the aspect ratio of the emote
		return f'<img src="{self.utils.emote_url(id)}" width=32px> | `:{name}:` | {author}'

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
		except ValueError as exception:
			logging.warning('steal_all: %s %s', type(exception).__name__, exception)
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
	@utils.typing
	async def steal_these(self, context, *emotes):
		"""Steal a bunch of custom emotes."""
		if not emotes:
			return await context.send('You need to provide one or more custom emotes.')

		messages = []
		for match in self.RE_CUSTOM_EMOTE.finditer(''.join(emotes)):
			name, id = match.groups()
			image_url = self.utils.emote_url(id)
			messages.append(await self.add_safe(name, image_url, context.author.id))
		# XXX this will fail if len > 2000
		await context.send(self.utils.fix_first_line(messages))

	## EVENTS

	async def on_message(self, message):
		"""Reply to messages containing :name: or ;name; with the corresponding emotes.
		This is like half the functionality of the bot"""
		if not self.bot.should_reply(message):
			return

		reply = await self.extract_emotes(message.content)
		if reply is not None:  # don't send empty whitespace
			self.replies[message.id] = await message.channel.send(reply)

	async def on_raw_message_edit(self, message_id, data):
		"""Ensure that when a message containing emotes is edited, the corresponding emote reply is, too."""

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
		result = self.utils.fix_first_line([await self.extract_emotes_line(line) for line in lines])

		if result.replace('\N{zero width space}', '').strip() != '':  # don't send an empty message
			return result

	async def extract_emotes_line(self, line: str) -> str:
		"""Extract emotes from a single line."""
		# RE_EMOTE uses the first group to match the same punctuation mark on both ends,
		# so the second group is the actual name
		names = [match.group(2) for match in self.RE_EMOTE.finditer(line)]
		if not names:
			return ''

		emotes = []
		for name in names:
			try:
				emotes.append(await self.get_formatted(name))
			except EmoteNotFoundError:
				pass

		return ''.join(emotes)

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
	async def fail_if_not_exists(self, name):
		if not await self.cog.exists(name):
			await self.send(f'`:{name}:` is not a valid emote.')
			# raise EmoteNotFoundError

	async def fail_on_bad_emote(self, name):
		# It may seem bad to do two identical database queries like this,
		# but I'm pretty sure asyncpg caches queries.
		await self.fail_if_not_exists(name)
		await self.fail_if_not_owner(name)


class ConnoisseurError(Exception):
	"""Generic error with the bot. This can be used to catch all bot errors."""
	pass


class HTTPException(ConnoisseurError):
	"""The server did not respond with an OK status code."""
	pass


class EmoteExistsError(ConnoisseurError):
	"""An emote with that name already exists"""
	pass


class EmoteNotFoundError(ConnoisseurError):
	"""An emote with that name was not found"""
	pass


class InvalidImageError(ConnoisseurError):
	"""The image is not a GIF, PNG, or JPG"""
	pass


class NoMoreSlotsError(ConnoisseurError):
	"""Raised in the rare case that all slots of a particular type (static/animated) are full
	if this happens, make a new Emoji Backend account, create 100 more guilds, and add the bot
	to all of these guilds.
	"""
	pass


class PermissionDeniedError(ConnoisseurError):
	"""Raised when a user tries to modify an emote they don't own"""
	pass


def setup(bot):
	bot.add_cog(Emotes(bot))
