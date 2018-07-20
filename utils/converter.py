#!/usr/bin/env python3
# encoding: utf-8

from discord.ext import commands

from .misc import get_message_by_offset


class HistoryMessage(commands.Converter):
	@classmethod
	async def convert(cls, context, argument):
		try:
			offset_or_id = int(argument)
		except ValueError:
			return await cls._get_message_by_keyword(context, argument)
		else:
			return await cls._get_message_by_number(offset_or_id)

	@staticmethod
	async def _get_message_by_keyword(context, argument):
		async for message in context.history():
			if message.id == context.message.id:
				continue  # skip the invoking message
			if argument.casefold() in message.content.casefold():
				return message

		raise commands.BadArgument('Message not found.')

	@classmethod
	async def _convert_from_number(cls, offset_or_id):
		if offset_or_id > 21154535154122752:  # smallest known snowflake
			id = offset_or_id
			return await cls._get_message_by_id(context.channel, id)
		elif offset_or_id < 0:
			offset = offset_or_id
			return await get_message_by_offset(context.channel, offset - 1)

	@staticmethod
	async def _get_message_by_id(channel, id):
		try:
			return await channel.get_message(id)
		except discord.NotFound:
			raise commands.BadArgument(
				'Message not found! Make sure your message ID is correct.') from None
		except discord.Forbidden:
			raise commands.BadArgument(
				'Permission denied! Make sure the bot has permission to read that message.') from None
