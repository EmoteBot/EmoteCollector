#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import imghdr
import functools
import re
import traceback

import aiohttp
import discord
from discord.ext import commands

from utils import log, typing


class Emotes:
	EMOTE_REGEX = re.compile(r'<a?:([\w_]{2,32}):(\d{15,21})>', re.ASCII)
	EMOTE_IN_TEXT_REGEX = re.compile(r'(?!<:)<?(;|:)([\w_]{2,32})(?!:\d+>)\1(?:\d+>)?', re.ASCII)

	def __init__(self, bot):
		self.bot = bot
		self.session = aiohttp.ClientSession()

	async def on_ready(self):
		self.guilds = []
		for guild in self.bot.guilds:
			# FIXME find a way to do this without hardcoding every backend account ID
			# If more backend accounts are needed, add them here.
			if guild.owner.id == 402664342182690816:
				self.guilds.append(guild)
		self.guilds.sort(key=lambda guild: guild.name)

	async def on_message(self, message):
		if message.author.bot:
			return

		names = []
		match = self.EMOTE_IN_TEXT_REGEX.search(message.content)
		for i, match in enumerate(self.EMOTE_IN_TEXT_REGEX.finditer(message.content)):
			try:
				names.append(match.group(2))
			except IndexError:
				pass
		if names:
			emotes = []
			for name in names:
				try:
					emotes.append(await self.get_formatted(name))
				except:
					#log('Retrieving', name, 'from the DB failed somehow.')
					#log(traceback.format_exc())
					pass
			if not emotes:
				return
			await message.channel.send(''.join(emotes))

	@commands.command()
	async def react(self, context, name, message: int = None, channel: int = None):
		"""Add a reaction to a message. Sad reacts only please.
		`ec/add <name> <message ID> [channel ID]`
		You can get the message ID by enabling developer mode (in Settings→Appearance),
		then right clicking on the message you want and clicking "Copy ID". Same for channel IDs.
		"""
		try:
			animated, name, emote_id, _ = await self.get(name)
		except EmoteNotFoundError:
			return await context.mock("%s doesn't exist!" % name)

		if channel is None:
			channel = context.channel
		else:
			channel = context.guild.get_channel(channel)

		try:
			message = await channel.get_message(message)
			emote_str = self.format_emote(animated, name, emote_id)[1:-1]
			await message.add_reaction(emote_str)
		except:
			log('React: failed to react with %s' % name)
			log(traceback.format_exc())
			return await context.mock('Failed to react with %s!' % name)

		def check(emote, message_id, channel_id, user_id):
			return (
				message_id == message.id
				and user_id == context.message.author.id
				and emote_id == getattr(emote, 'id', None))  # unicode emoji have no id

		try:
			await self.bot.wait_for('raw_reaction_add', timeout=30, check=check)
		except asyncio.TimeoutError:
			log("react: user didn't react in time")
		finally:
			await asyncio.sleep(0.5)
			await message.remove_reaction(emote_str, context.guild.me)

	@commands.command()
	async def react2(self, context, message: int = None):
		emote_str = ':test:407030315194777600'
		message = await channel.get_message(message)
		await message.add_reaction(emote_str)

		def check(reaction, user):
			print('Got reaction', reaction.emoji)
			checks = (
				reaction.message.id == message.id,
				user == context.message.author,
				id == getattr(reaction.emoji, 'id', None))  # unicode emoji have no id
			for check in checks:
				print(check)
			return all(checks)

		try:
			await self.bot.wait_for('reaction_add', timeout=30, check=check)
		except asyncio.TimeoutError:
			await message.remove_reaction(emote_str, context.guild.me)


	@commands.command(aliases=['remove'])
	async def delete(self, context, name):
		"""Deletes an emote from the bot. You must own it."""
		success_message = '%s successfully deleted.' % name

		try:
			animated, name, id, author = await self.get(name)
		except EmoteNotFoundError:
			return await context.mock("%s doesn't exist!" % name)
		if author != context.author.id:
			return await context.mock(
				"You're not the author of %s!" % self.format_emote(animated, name, id, author))
		log('Trying to delete', name, id)

		await self.bot.db.execute('DELETE FROM connoisseur.emojis WHERE name ILIKE $1', name)
		emote = self.bot.get_emoji(id)
		if emote is not None:
			log(name, 'twas in the cache')
			await emote.delete()
			return await context.send(success_message)

		log(name, 'twas not in the cache')
		try:
			emote = await self.find_emote_in_guilds(id)
		except EmoteNotFoundError:
			return log('Emote %s not found in the guilds, but found in the database!' % name)
		else:
			await emote.delete()
			return await context.send(success_message)

	@commands.command()
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
			if match is not None:
				name, id = match.groups()
				url = self.emote_url(id)
			else:
				await context.mock("That's not an emote!")
				return
		elif len(args) == 2:
			# finally, an easy case
			name = args[0]
			match = self.EMOTE_REGEX.match(args[1])
			if match is None:
				url = args[1]
			else:
				url = self.emote_url(match.group(2))

		await self.add_safe(context, name, url)

	async def add_safe(self, context, name, url):
		try:
			message = await self.add_(name, url, context.message.author.id)
		except EmoteExistsError:
			await context.mock('An emote already exists with that name!')
		else:
			await context.send(message)

	async def add_(self, name, url, author_id):
		try:
			await self.get(name)
		except EmoteNotFoundError:
			image_data = await self.fetch(url)
			image_type = imghdr.what(None, image_data)
			if imghdr.test_gif(image_data, None) == 'gif':
				animated = True
			elif imghdr.test_png(image_data, None) == 'png' or imghdr.test_jpeg(image_data, None) == 'jpeg':
				animated = False
			else:
				raise InvalidImageError

			guild = await self.current_guild(animated)
			emote = await guild.create_custom_emoji(name=name, image=image_data)
			await self.bot.db.execute(
				'INSERT INTO connoisseur.emojis(name, id, author, animated) VALUES($1, $2, $3, $4)',
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

	async def current_guild(self, animated=False):
		for guild in self.guilds:
			if sum(1 for emote in guild.emojis if animated == emote.animated) < 50:
				return guild
		raise NoMoreSlotsError('This bot too weak! Try adding more guilds.')

	async def get(self, name):
		row = await self.bot.db.fetchrow('''
			SELECT *
			FROM connoisseur.emojis
			WHERE name ILIKE $1''',
			name)
		if row is None:
			raise EmoteNotFoundError('Emote %s not found in the database!' % name)
		return row['animated'], row['name'], row['id'], row['author']

	async def get_formatted(self, name):
		return self.format_emote(*(await self.get(name))[:-1])

	async def find_emote_in_guilds(self, id):
		for guild in self.guilds:
			emote = discord.utils.get(guild.emojis, id=id)
			if emote is not None:
				return emote
		raise EmoteNotFoundError('An emote with ID %s was not found in any guild.' % id)

	@staticmethod
	def emote_url(id):
		return 'https://cdn.discordapp.com/emojis/%s' % id

	@staticmethod
	def format_emote(animated, name, id):
		return '<%s:%s:%s>' % ('a' if animated else '', name, id)


class NoMoreSlotsError(Exception):
	"""Raised in the rare case that all slots of a particular type (static/animated) are full
	if this happens, make a new Emoji Backend account, create 100 more guilds, and add the bot
	to all these guilds
	"""
	pass


class EmoteExistsError(Exception):
	"""An emote with that name already exists"""
	pass


class EmoteNotFoundError(Exception):
	"""An emote with that name was not found"""
	pass


class InvalidImageError(Exception):
	"""The image is not a GIF, PNG, or JPG"""
	pass


def setup(bot):
	bot.add_cog(Emotes(bot))
