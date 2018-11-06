#!/usr/bin/env python3
# encoding: utf-8

import re
import typing

import discord
from discord.ext import commands

from .. import utils

class TooLewdError(commands.BadArgument):
	"""An NSFW emote was used in an SFW channel"""
	def __init__(self, name):
		self.name = name
		super().__init__(_('`{name}` is NSFW, but this channel is SFW.').format(**locals()))

class DatabaseEmoteConverter(commands.Converter):
	def __init__(self, *, check_nsfw=True):
		self.check_nsfw = check_nsfw

	async def convert(self, context, name: str):
		name = name.strip().strip(':;')
		cog = context.bot.get_cog('Database')
		emote = await cog.get_emote(name)
		if self.check_nsfw and emote.is_nsfw and not getattr(context.channel, 'nsfw', True):
			raise TooLewdError(emote.name)
		return emote

UserOrMember = typing.Union[discord.Member, discord.User]

async def convert_offset(context, channel, offset):
	try:
		offset = int(offset, base=0) - 1  # skip the invoking message
	except ValueError:
		raise commands.BadArgument(_('Not a valid integer.'))

	if offset == 0:
		# not sure why this should be allowed, but i see no reason to disallow it either.
		return message
	if offset < 0:
		return await utils.get_message_by_offset(channel, offset)

	raise commands.BadArgument(_('Not a message offset.'))

def Snowflake(argument: str):
	try:
		id = int(argument)
	except ValueError:
		raise commands.BadArgument(_('Not a valid integer.'))

	if id < utils.SMALLEST_SNOWFLAKE:
		raise commands.BadArgument(_('Not a valid message ID.'))

	return id

async def convert_id(context, channel, id: str):
	id = Snowflake(id)

	try:
		return await channel.get_message(id)
	except discord.NotFound:
		raise commands.BadArgument(_(
			'Message not found! Make sure your message ID is correct.')) from None
	except discord.Forbidden:
		raise commands.BadArgument(_(
			'Permission denied! Make sure the bot has permission to read that message.')) from None

_member_converter = commands.converter.MemberConverter()

async def convert_member(context, channel, argument):
	member = await _member_converter.convert(context, argument)

	def predicate(message):
		return (
			message.id != context.message.id
			and message.author == member)

	return await _search_for_message(context, predicate)

async def convert_keyword(context, channel, argument):
	argument = argument.lower()

	def normalize(message):
		# make sure that 1234 doesn't match <:emote:1234>
		return re.sub(utils.lexer.t_CUSTOM_EMOTE, lambda match: f':{match["name"]}:', message).lower()

	def predicate(message):
		return message.id != context.message.id and argument in normalize(message.content)

	return await _search_for_message(channel, predicate)

async def _search_for_message(target, predicate):
	message = await target.history().find(predicate)
	if message is None:
		raise commands.BadArgument(_('Message not found.'))
	return message

class Message(commands.Converter):
	_channel_converter = commands.converter.TextChannelConverter()

	@classmethod
	async def convert(cls, context, argument):
		channel, argument = await cls._parse_argument(context, argument)
		await cls._check_reaction_permissions(context, channel)

		for converter in convert_offset, convert_id, convert_member, convert_keyword:
			try:
				return await converter(context, channel, argument)
			except commands.CommandError as exception:
				pass

		raise commands.BadArgument(_(
			'Failed to interpret that as a message offset, message ID, or user, '
			'or failed to find a message containing that search keyword.'))

	@classmethod
	async def _parse_argument(cls, context, argument) -> typing.Tuple[discord.abc.Messageable, str]:
		channel, slash, message = argument.partition('/')
		# allow spaces around the "/"
		channel = channel.rstrip()
		message = message.lstrip()
		if channel:
			try:
				channel = await cls._channel_converter.convert(context, channel)
				return channel, message
			except commands.BadArgument:
				pass

		return context.channel, argument

	@staticmethod
	async def _check_reaction_permissions(context, channel):
		# author might not be a Member, even in a guild, if it's a webhook.
		if not context.guild or not isinstance(context.author, discord.Member):
			return

		sender_permissions = channel.permissions_for(context.author)
		permissions = channel.permissions_for(context.guild.me)

		if not sender_permissions.read_message_history or not permissions.read_message_history:
			raise commands.CheckFailure(_('Unable to react: you and I both need permission to read message history.'))
		if not sender_permissions.add_reactions or not permissions.add_reactions:
			raise commands.CheckFailure(_('Unable to react: you and I both need permission to add reactions.'))
		if not sender_permissions.external_emojis or not permissions.external_emojis:
			raise commands.CheckFailure(_('Unable to react: you and I both need permission to use external emotes.'))
