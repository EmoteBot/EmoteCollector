# Emote Collector collects emotes from other servers for use by people without Nitro
# Copyright © 2018–2019 lambda#0987
#
# Emote Collector is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Emote Collector is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Emote Collector. If not, see <https://www.gnu.org/licenses/>.

import inspect
import re
import typing

import discord
from discord.ext import commands
from discord.ext.commands.view import StringView

from .errors import EmoteNotFoundError, TooLewdError
from .. import utils
from ..extensions.db import DatabaseEmote


class _MultiConverter(commands.Converter):
	def __init__(self, *, converters=None):
		self.converters = converters

	def __getitem__(self, params):
		return type(self)(converters=params)

	async def convert(self, ctx, argument):
		converted = []
		view = StringView(argument)
		while not view.eof:
			args = []
			for converter in self.converters:
				view.skip_ws()
				arg = view.get_quoted_word()
				if arg is None:
					raise commands.UserInputError(_('Not enough arguments.'))
				args.append(await self._do_conversion(ctx, converter, arg))
			converted.append(tuple(args))
		return converted

	async def _do_conversion(self, ctx, converter, arg):
		if inspect.isclass(converter) and issubclass(converter, commands.Converter):
			return await converter().convert(ctx, arg)
		if isinstance(converter, commands.Converter):
			return await converter.convert(ctx, arg)
		if callable(converter):
			return converter(arg)
		raise TypeError

MultiConverter = _MultiConverter()

class DatabaseEmoteConverter(commands.Converter):
	def __init__(self, *, check_nsfw=True):
		self.check_nsfw = check_nsfw

	async def convert(self, context, name: str):
		name = name.strip().strip(':;')
		cog = context.bot.cogs['Database']
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
		return await channel.fetch_message(id)
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

LINKED_EMOTE = (
	r'(?a)\[(?P<name>\w{2,32})\]\(https://cdn\.discordapp'
	r'\.com/emojis/(?P<id>\d{17,})\.(?P<extension>\w+)(?:\?v=1)?\)'
)

class LoggedEmote(commands.Converter):
	async def convert(self, ctx, argument):
		message = await commands.converter.MessageConverter().convert(ctx, argument)

		if message.channel not in ctx.bot.cogs['Logger'].channels:
			raise commands.BadArgument(_('That message is not from a log channel.'))

		try:
			embed = message.embeds[0]
		except IndexError:
			raise commands.BadArgument(_('No embeds were found in that message.'))

		m = re.match(LINKED_EMOTE, embed.description) or re.match(utils.lexer.t_CUSTOM_EMOTE, embed.description)
		try:
			return await ctx.bot.cogs['Database'].get_emote(m['name'])
		except EmoteNotFoundError:
			d = m.groupdict()
			d['nsfw'] = 'MOD_NSFW'
			d['id'] = int(d['id'])
			d['animated'] = d.get('extension') == 'gif' or bool(d.get('animated'))
			return DatabaseEmote(d)

# because MultiConverter does not support Union
class DatabaseOrLoggedEmote(commands.Converter):
	def __init__(self, *, check_nsfw=True):
		self.db_conv = DatabaseEmoteConverter(check_nsfw=check_nsfw)

	async def convert(self, ctx, argument):
		err = None
		try:
			logged_emote = await LoggedEmote().convert(ctx, argument)
		except commands.CommandError as exc:
			pass
		else:
			return logged_emote

		try:
			db_emote = await self.db_conv.convert(ctx, argument)
		except commands.CommandError as exc:
			raise commands.BadArgument(
				_('Failed to interpret {argument} as a logged emote message or an emote in my database.')
				.format(argument=argument))

		return db_emote

class Guild(commands.Converter):
	async def convert(self, ctx, argument):
		try:
			guild_id = int(argument)
		except ValueError:
			guild = discord.utils.get(ctx.bot.guilds, name=argument)
		else:
			guild = ctx.bot.get_guild(guild_id)

		if guild is None:
			raise commands.BadArgument(_('Server not found.'))

		return guild
