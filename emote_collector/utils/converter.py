#!/usr/bin/env python3
# encoding: utf-8

import re
import typing

from discord.ext import commands

from .. import utils

class OffsetMessage(commands.Converter):
	@staticmethod
	async def convert(context, offset):
		try:
			offset = int(offset, base=0) - 1  # skip the invoking message
		except ValueError:
			raise commands.BadArgument(_('Not a valid integer.'))

		if offset == 0:
			# not sure why this should be allowed, but i see no reason to disallow it either.
			return context.message
		if offset < 0:
			return await utils.get_message_by_offset(context.channel, offset)

		raise commands.BadArgument(_('Not a message offset.'))

def _validate_snowflake(argument: str):
	try:
		id = int(argument)
	except ValueError:
		raise commands.BadArgument(_('Not a valid integer.'))

	if id < utils.SMALLEST_SNOWFLAKE:
		raise commands.BadArgument(_('Not a valid message ID.'))

	return id

class IDMessage(commands.Converter):
	@staticmethod
	async def convert(context, id):
		id = _validate_snowflake(id)

		try:
			return await context.channel.get_message(id)
		except discord.NotFound:
			raise commands.BadArgument(_(
				'Message not found! Make sure your message ID is correct.')) from None
		except discord.Forbidden:
			raise commands.BadArgument(_(
				'Permission denied! Make sure the bot has permission to read that message.')) from None

async def _search_for_message(target, predicate):
	async for message in target.history():
		if predicate(message):
			return message

	raise commands.BadArgument(_('Message not found.'))

class MemberMessage(commands.Converter):
	_member_converter = commands.converter.MemberConverter()

	@classmethod
	async def convert(cls, context, argument):
		member = await cls._member_converter.convert(context, argument)

		def predicate(message):
			return (
				message.id != context.message.id
				and message.author == member)

		return await _search_for_message(context, predicate)

class KeywordMessage(commands.Converter):
	@staticmethod
	async def convert(context, argument):
		def normalize(message):
			return re.sub(utils.lexer.t_CUSTOM_EMOTE, lambda match: f':{match["name"]}:', message).lower()

		def predicate(message):
			return message.id != context.message.id and argument.lower() in normalize(message.content)

		return await _search_for_message(context, predicate)

Message = typing.Union[OffsetMessage, IDMessage, MemberMessage, KeywordMessage]
