#!/usr/bin/env python3
# encoding: utf-8

import typing

import aiocache
import discord
from discord.ext import commands

from ..utils import i18n

cached = aiocache.cached(ttl=20)
Location = typing.Union[discord.TextChannel, discord.Member]

class Locales:
	def __init__(self, bot):
		self.bot = bot
		self.pool = self.bot.pool

	@commands.group(name='locale')
	async def locale_command(self, context):
		""""Commands relating to modifying the locale.
		This command does nothing on its own; all functionality is in subcommands.
		"""
		pass

	@locale_command.command(name='get')
	async def get_locale_command(self, context, location: Location = None):
		"""Get the locale for a channel, user, or the entire server.

		location: A text channel or user.
		You can only get your user locale, unless you have the Manage Messages permission.
		If location is not provided, get the server locale.
		"""

		if location is None:
			if context.guild is None:
				return await context.send(_("You can't get the server locale in DMs."))

			guild_locale = await self.guild_locale(context.guild.id)
			if not guild_locale:
				guild_locale = i18n.default_locale
			return await context.send(_('The current locale for this server is: {guild_locale}').format(
				**locals()))

		if isinstance(location, discord.TextChannel):
			channel_or_guild_locale = await self.channel_or_guild_locale(location)
			if not channel_or_guild_locale:
				channel_or_guild_locale = i18n.default_locale
			return await context.send(_(
				'The current locale for that channel is: {channel_or_guild_locale}').format(**locals()))

		if location != context.author and not context.author.guild_permissions.manage_messages:
			return await context.send(_('You can only get your own locale.'))
		user_locale = await self.locale(context.message)
		return await context.send(_('The current locale for that user  	is: {user_locale}').format(**locals()))

	@locale_command.command(name='set')
	async def set_locale_command(self, context, locale, location: Location = None):
		"""Set the locale for a channel, user, or the entire server.

		location: A text channel or user.
		You can only get your user locale, unless you have the Manage Messages permission.
		If location is not provided, get the server locale.
		"""

		if locale not in i18n.locales:
			return await context.send(_('Invalid locale. The valid locales are: {locales}').format(
				locales=', '.join(i18n.locales)))

		if not isinstance(location, discord.Member) and not context.guild:
			return await context.send(_('Cannot set the server or channel locale in DMs.'))

		if (
			not isinstance(location, discord.Member)
			and not context.author.guild_permissions.manage_messages
		):
			raise commands.MissingPermissions(('manage_messages',))

		if not location:
			if not context.guild:
				return await context.send(_('Cannot set the server locale in DMs.'))
			await self.set_guild_locale(context.guild.id, locale)

		if isinstance(location, discord.TextChannel):
			await self.set_channel_locale(context.guild.id, location.id, locale)

		elif isinstance(location, discord.Member):
			if context.author != location:
				return await context.send(_('You cannot set the locale of another user.'))
			await self.set_user_locale(location.id, locale)

		await context.send(_(
			'✅ Locale set. Note that it may take up to 20 seconds for your changes to take effect.'))

	@cached
	async def locale(self, message):
		if not message.guild:
			return await self.user_locale(message.author.id)

		# can't wait for :=
		user_locale = await self.user_locale(message.webhook_id or message.author.id)
		if user_locale:
			return user_locale

		channel_or_guild_locale = await self.channel_or_guild_locale(message)
		if channel_or_guild_locale:
			return channel_or_guild_locale

		return i18n.default_locale

	async def channel_or_guild_locale(self, location_or_message: typing.Union[Location, discord.Message]):
		if isinstance(location_or_message, discord.TextChannel):
			return await self._channel_locale(channel=location_or_message)

		message = location_or_message
		if not message.guild:
			return i18n.default_locale

	async def _channel_locale(self, channel):
		channel_locale = await self.channel_locale(channel.id)
		if channel_locale:
			return channel_locale

		guild_locale = await self.guild_locale(channel.guild.id)
		if guild_locale:
			return guild_locale

	@cached
	async def guild_locale(self, guild):
		return await self.pool.fetchval("""
			SELECT locale
			FROM   locales
			WHERE      guild = $1
			       AND channel IS NULL
			       AND "user" IS NULL
		""", guild)

	@cached
	async def channel_locale(self, channel):
		return await self.pool.fetchval("""
			SELECT locale
			FROM   locales
			WHERE      channel = $1
			       -- guild may or may not be null
			       AND "user" IS NULL
		""", channel)

	@cached
	async def user_locale(self, user):
		return await self.pool.fetchval("""
			SELECT locale
			FROM   locales
			WHERE      "user" = $1
			       AND guild IS NULL
			       AND channel IS NULL
		""", user)

	async def set_guild_locale(self, guild, locale):
		# connection/transaction probably isn't necessary for this, right?
		await self.pool.execute("""
			DELETE FROM
			locales
			WHERE     guild = $1
			      AND channel IS NULL
			      AND "user"  IS NULL;
		""", guild)
		await self.pool.execute("""
			INSERT INTO locales (guild, locale)
			VALUES ($1, $2);
		""", guild, locale)

	async def set_channel_locale(self, guild, channel, locale):
		await self.pool.execute("""
			INSERT INTO locales (guild, channel, locale)
			VALUES ($1, $2, $3)
			ON CONFLICT (guild, channel) DO UPDATE
			SET locale = EXCLUDED.locale
		""", guild, channel, locale)

	async def set_user_locale(self, user, locale):
		await self.pool.execute("""
			INSERT INTO locales ("user", locale)
			VALUES ($1, $2)
			ON CONFLICT ("user") DO UPDATE
			SET locale = EXCLUDED.locale
		""", user, locale)

def setup(bot):
	bot.add_cog(Locales(bot))
