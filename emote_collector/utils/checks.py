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

from discord.ext import commands

from .errors import BlacklistedError

# Used under the MIT license. Copyright (c) 2017 BeatButton
# https://github.com/BeatButton/beattie/blob/44fd795aef7b1c19233510cda8046baab5ecabf3/utils/checks.py
def owner_or_permissions(**perms):
	"""Checks if the member is a bot owner or has any of the permissions necessary."""
	async def predicate(ctx):
		if await ctx.bot.is_owner(ctx.author):
			return True
		permissions = ctx.channel.permissions_for(ctx.author)
		return any(getattr(permissions, perm, None) == value
				   for perm, value in perms.items())
	return commands.check(predicate)

def is_moderator():
	async def predicate(context):
		db = context.bot.get_cog('Database')
		if not await db.is_moderator(context.author.id):
			raise commands.CheckFailure(_('You must be an emote moderator to run this command.'))
		return True
	return commands.check(predicate)

def not_blacklisted():
	async def predicate(context):
		db = context.bot.get_cog('Database')
		blacklist_reason = await db.get_user_blacklist(context.author.id)
		if blacklist_reason is None:
			return True
		raise BlacklistedError(context.prefix, blacklist_reason)

	return commands.check(predicate)
