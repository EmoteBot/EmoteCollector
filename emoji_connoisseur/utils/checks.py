#!/usr/bin/env python3
# encoding: utf-8

from discord.ext import commands


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


def not_blacklisted():
	async def predicate(context):
		db = context.cog.db
		blacklist_reason = await db.get_user_blacklist(context.author.id)
		if blacklist_reason is None:
			return True
		await context.send(
			f'Sorry, you have been blacklisted with the reason `{blacklist_reason}`. '
			f'To appeal, please join the support server with `{context.prefix}support`.')
		return False
	return commands.check(predicate)
