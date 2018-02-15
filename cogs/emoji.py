#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import imghdr
from io import StringIO
import logging
import random
import re
import traceback

import aiohttp
from bs4 import BeautifulSoup
import discord
from discord.ext import commands

from cogs.utils import checks
from utils import create_gist, is_owner, typing


logger = logging.getLogger('cogs.emoji')


class Emotes:
	EMOTE_REGEX = re.compile(r'<a?:([\w_]{2,32}):(\d{15,21})>', re.ASCII)
	EMOTE_IN_TEXT_REGEX = re.compile(r'(?!<:)<?(;|:)([\w_]{2,32})(?!:\d+>)\1(?:\d+>)?', re.ASCII)

	def __init__(self, bot):
		self.bot = bot
		self.bot.loop.create_task(self.find_backend_guilds())
		self.session = aiohttp.ClientSession()

		# Keep track of replies so that if the user edits/deletes a message,
		# we delete/edit the corresponding reply.
		self.replies = {}

	def __unload(self):
		self.session.close()

	async def find_backend_guilds(self):
		if hasattr(self, 'guilds') and self.guilds:
			return

		while not self.bot.is_ready():
			await asyncio.sleep(0.1)

		self.guilds = []
		for guild in self.bot.guilds:
			if await self.bot.is_owner(guild.owner):
				self.guilds.append(guild)
		logger.info('In ' + str(len(self.guilds)) + ' backend guilds.')

	async def on_message(self, message):
		if message.author.bot:
			return

		emotes = await self.extract_emotes(message.content)
		if emotes:
			self.replies[message.id] = await message.channel.send(emotes)

	async def on_raw_message_edit(self, message_id, data):
		if message_id not in self.replies or 'content' not in data:
			return

		emotes = await self.extract_emotes(data['content'])
		reply = self.replies[message_id]
		if not emotes:
			return await reply.delete()
		elif emotes == reply.content:
			# don't edit a message if we don't need to
			return

		await reply.edit(content=emotes)

	async def on_raw_message_delete(self, message_id, channel_id):
		try:
			await self.replies.pop(message_id).delete()
		except KeyError:
			pass

	async def on_raw_bulk_message_delete(self, message_ids, channel_id):
		messages = (self.replies.pop(id) for id in message_ids if id in self.replies)
		try:  # this will only work if we have manage_messages in that channel
			await self.bot.delete_messages(messages)
		except discord.Forbidden:
			for message in messages:  # should always work, since these are our messages
				await message.delete()

	async def extract_emotes(self, message: str):
		names = []
		for match in self.EMOTE_IN_TEXT_REGEX.finditer(message):
			try:
				names.append(match.group(2))
			except IndexError:
				pass

		if not names:
			return

		emotes = []
		for name in names:
			try:
				emotes.append(await self.get_formatted(name))
			except EmoteNotFoundError:
				pass
		if not emotes:
			return

		return ''.join(emotes)

	@commands.command(aliases=['create'])
	@typing
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
			# as far as i can tell, this is how discord replaces filenames
			name = args[0] if args else attachment.filename.split('.')[0].replace(' ', '')
			url = attachment.url

		elif len(args) == 1:
			match = self.EMOTE_REGEX.match(args[0])
			if match is None:
				return await context.send("That's not an emote!")
			else:
				name, id = match.groups()
				url = self.emote_url(id)

		elif len(args) == 2:
			# finally, an easy case
			name = args[0]
			match = self.EMOTE_REGEX.match(args[1])
			if match is None:
				url = args[1]
			else:
				url = self.emote_url(match.group(2))

		else:
			return await context.send('Your message had no emotes and no name!')

		await self.add_safe(context, name, url)

	@commands.command(aliases=['delete', 'delet'])
	@typing
	async def remove(self, context, name):
		"""Removes an emote from the bot. You must own it."""
		await context.fail_on_bad_emote(name)
		animated, name, id, author = await self.get(name)
		success_message = '%s successfully deleted.' % name

		logger.debug('Trying to delete ', name, id)

		await self.bot.db.execute('DELETE FROM emojis WHERE name ILIKE $1', name)
		emote = self.bot.get_emoji(id)
		if emote is not None:
			logger.debug(name + " 'twas in the cache")
			await emote.delete()
			return await context.send(success_message)
		else:
			logger.error(name + " 'twas not in the cache!")

	@commands.command()
	@typing
	async def rename(self, context, old_name, new_name):
		"""Renames an emote. You must own it."""
		await context.fail_on_bad_emote(old_name)
		animated, old_name, id, author = await self.get(old_name)

		try:
			await self.rename_(id, new_name)
		except discord.Forbidden:
			await context.send(
				'Unable to rename the emote because of missing permissions. This should not happen.\n'
				'Please contact @null byte#1337.')
			logger.error('Missing permissions to rename ' + old_name)
			logger.error(traceback.format_exc())
		except discord.HTTPException as exception:
			await context.send(self.format_http_exception(exception))
			logger.error('Rename:')
			logger.error(traceback.format_exc())
		else:
			await context.send('Emote successfully renamed.')

	@commands.command()
	async def react(self, context, name, message, channel: int = None):
		"""Add a reaction to a message. Sad reacts only please.
		`ec/add <name> <message ID> [channel ID]`
		You can get the message ID by enabling developer mode (in Settings→Appearance),
		then right clicking on the message you want and clicking "Copy ID". Same for channel IDs.
		"""
		await context.fail_if_not_exists(name)
		animated, name, emote_id, _ = await self.get(name)

		if channel is None:
			channel = context.channel
		else:
			channel = context.guild.get_channel(channel)

		try:
			message = await channel.get_message(message)
		except discord.NotFound:
			return await context.send(
				'Message not found! Make sure your message and channel IDs are correct.')
		except discord.Forbidden:
			return await context.send(
				'Permission denied! Make sure the bot has permission to read that message.')

		# there's no need to react to a message if that reaction already exists
		if discord.utils.find(lambda reaction: reaction.emoji.id == emote_id, message.reactions):
			return await context.send('You can already react to that message, silly!', delete_after=5)

		emote_str = self.format_emote(animated, name, emote_id)[1:-1]  # skip the <>

		try:
			await message.add_reaction(emote_str)
		except discord.HTTPException as ex:
			error_message = 'Failed to react with %s\n%s' % (name, self.format_http_exception(ex))
			logger.error('react: ' + error_message)
			logger.error(traceback.format_exc())
			return await context.send(error_message)
		except discord.Forbidden:
			# these errors are not severe enough to log
			return await context.send(
				'Permission denied! Make sure the bot has permission to react to that message.')

		def check(emote, message_id, channel_id, user_id):
			return (
				message_id == message.id
				and user_id == context.message.author.id
				and emote_id == getattr(emote, 'id', None))  # unicode emoji have no id

		try:
			await self.bot.wait_for('raw_reaction_add', timeout=30, check=check)
		except asyncio.TimeoutError:
			logger.info("react: user didn't react in time")
		finally:
			await asyncio.sleep(0.6)
			await message.remove_reaction(emote_str, context.guild.me)
			try:
				await context.message.delete()
			except discord.errors.Forbidden:
				pass

	@commands.command()
	@typing
	async def list(self, context, user: discord.User = None):
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

		await context.send(await create_gist('list.md', table.getvalue()))

	@commands.command()
	async def find(self, context, name):
		"""Internal command to find out which backend server a given emote is in.
		This is useful because emotes are added to random guilds to avoid rate limits.
		"""
		await context.fail_if_not_exists(name)
		animated, name, id, author = await self.get(name)
		emote = self.bot.get_emoji(id)

		if emote is None:
			error_message = '%s was not in the cache!' % name
			logger.error('find: ' + error_message)
			return await context.send(error_message)

		return await context.send('%s is in %s.' % (emote.name, emote.guild.name))

	@commands.command(name='steal-all', hidden=True)
	@checks.is_owner()
	async def steal_all(self, context, list_url):
		"""Steal all emotes listed on a markdown file given by list_url.
		This file must have the same format as the one generated by Element Zero's e0list command.
		"""
		async with self.session.get(list_url) as resp:
			text = await resp.text()
		emotes = self.parse_list(text)
		for name, image, author in emotes:
			try:
				message = await self.add_(name, image, author)
			except EmoteExistsError:
				await context.send('An emote already exists with that name!')
			else:
				await context.send(message)

	async def get(self, name):
		row = await self.bot.db.fetchrow("""
			SELECT *
			FROM emojis
			WHERE name ILIKE $1""",
			name)
		if row is None:
			raise EmoteNotFoundError(name)
		return row['animated'], row['name'], row['id'], row['author']

	async def get_formatted(self, name):
		return self.format_emote(*(await self.get(name))[:-1])

	@staticmethod
	def format_emote(animated, name, id):
		return '<%s:%s:%s>' % ('a' if animated else '', name, id)

	async def add_safe(self, context, name, url):
		try:
			message = await self.add_(name, url, context.message.author.id)
		except EmoteExistsError:
			await context.send('An emote already exists with that name!')
		except discord.HTTPException as ex:
			error_message = (
				'An error occurred while creating the emote:\n'
				+ self.format_http_exception(ex))
			await context.send(error_message)
			logger.error(traceback.format_exc())
		else:
			await context.send(message)

	async def add_(self, name, url, author_id):
		try:
			await self.get(name)
		except EmoteNotFoundError:
			image_data = await self.fetch(url)
			if imghdr.test_gif(image_data, None) == 'gif':
				animated = True
			elif imghdr.test_png(image_data, None) == 'png' or imghdr.test_jpeg(image_data, None) == 'jpeg':
				animated = False
			else:
				raise InvalidImageError

			guild = self.free_guild(animated)
			emote = await guild.create_custom_emoji(name=name, image=image_data)
			await self.bot.db.execute(
				'INSERT INTO emojis(name, id, author, animated) VALUES($1, $2, $3, $4)',
				name,
				emote.id,
				author_id,
				animated)
			return 'Emote %s successfully created.' % emote
		else:
			raise EmoteExistsError

	async def fetch(self, url):
		async with self.session.get(url) as resp:
			return await resp.read()

	@staticmethod
	def emote_url(id):
		return 'https://cdn.discordapp.com/emojis/%s' % id

	def free_guild(self, animated=False):
		"""Find a guild in the backend guilds suitable for storing an emote.

		As the number of emotes stored by the bot increases, the probability of finding a rate-limited
		guild approaches 1, but until then, this should work pretty well.
		"""
		free_guilds = []
		for guild in self.guilds:
			if sum(1 for emote in guild.emojis if animated == emote.animated) < 50:
				free_guilds.append(guild)

		if not free_guilds:
			raise NoMoreSlotsError('This bot too weak! Try adding more guilds.')

		# hopefully this lets us bypass the rate limit more often, since emote rates are per-guild
		return random.choice(free_guilds)

	async def rename_(self, id, new_name):
		emote = self.bot.get_emoji(id)
		await emote.edit(name=new_name)
		await self.bot.db.execute('UPDATE emojis SET name = $2 WHERE id = $1', id, new_name)

	def parse_list(self, text):
		rows = [line.split(' | ') for line in text.split('\n')[2:]]
		image_column = (row[0] for row in rows)
		soup = BeautifulSoup(''.join(image_column), 'lxml')
		images = soup.find_all(attrs={'class': 'emoji'})
		image_urls = [image.get('src') for image in images]
		names = [row[1].replace('`', '').replace(':', '') for row in rows if len(row) > 1]
		authors = [row[2].split()[-1].replace('(', '').replace(')', '') for row in rows if len(row) > 2]

		return zip(names, image_urls, authors)

	def format_row(self, record):
		name, id, author, _ = record
		user = self.bot.get_user(author)
		if user is None:
			author = 'Unknown user with ID %s' % author
		else:
			author = '%s (%s)' % (user, user.id)
		# only set the width in order to preserve the aspect ratio of the emote
		return ('<img src="%s" width=32px> | `%s` | %s' %
			(self.emote_url(id), name, author))

	@staticmethod
	def format_http_exception(exception):
		return '{} (status code: {}):\n{}'.format(
			exception.response.reason, exception.response.status, exception.text)


class EmoteContext(commands.Context):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)

	async def fail_if_not_exists(self, name):
		try:
			animated, name, id, author = await self.cog.get(name)
		except EmoteNotFoundError:
			await self.send(name + ' is not a valid emote')
			logger.error(traceback.format_exc())

	async def fail_if_not_owner(self, name):
		# assume that it exists, because it has to exist for anyone to be its owner
		# also, fail_if_not_exists should do this anyway
		animated, name, id, author = await self.cog.get(name)

		# By De Morgan's laws, this is equivalent to (not is_owner and not emote_author)
		# but I think this is clearer :P
		if not (await is_owner(self) or author == self.author.id):
			await self.send(
				"You're not the author of %s!" % self.cog.format_emote(animated, name, id))
			raise PermissionDeniedError

	async def fail_on_bad_emote(self, name):
		# It may seem bad to do two identical database queries like this,
		# but I'm pretty sure asyncpg caches queries.
		await self.fail_if_not_exists(name)
		await self.fail_if_not_owner(name)


class ConnoisseurError(Exception):
	"""Generic error with the bot. This can be used to catch all bot errors."""
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
