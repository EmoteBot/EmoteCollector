#!/usr/bin/env python3
# encoding: utf-8

import typing

from discord.ext import commands

import utils


class OffsetMessage(commands.Converter):
	@staticmethod
	async def convert(context, offset):
		if offset is None:
			# get the second to last message (skip the invoking message)
			offset = -2
		if offset < 0:
			return await utils.get_message_by_offset(context.channel, offset)

		raise commands.BadArgument('Not a message offset.')

class IDMessage(commands.Converter):
	@staticmethod
	async def convert(context, id):
		if offset < utils.SMALLEST_SNOWFLAKE:
			raise commands.BadArgument('Not a valid message ID.')

		try:
			return await context.channel.get_message(id)
		except discord.NotFound:
			raise commands.BadArgument(
				'Message not found! Make sure your message ID is correct.') from None
		except discord.Forbidden:
			raise commands.BadArgument(
				'Permission denied! Make sure the bot has permission to read that message.') from None

class KeywordMessage(commands.Converter):
	@staticmethod
	async def convert(context, argument):
		def emote_to_name(match):
			return match.group('name')

		def normalize(message):
			return utils.emote.RE_CUSTOM_EMOTE.sub(emote_to_name, message).casefold()

		async for message in context.history():
			if message.id == context.message.id:
				continue  # skip the invoking message
			if argument.casefold() in normalize(message.content):
				return message

		raise commands.BadArgument('Message not found.')

Message = typing.Union[OffsetMessage, IDMessage, KeywordMessage]
