#!/usr/bin/env python3
# encoding: utf-8

"""a selfbot that creates guilds"""

import os
import sys
import time
import typing
import asyncio
import inspect
import functools
import contextlib

import discord

bot = discord.Client()

def print_status(status_message):
	class print_messages:
		def __enter__(self):
			print(status_message + '...', end=' ', file=sys.stderr, flush=True)
		def __exit__(self, *excinfo):
			print('done.', file=sys.stderr)

	def wrapper(func):
		if inspect.iscoroutinefunction(func):
			async def wrapped(*args, **kwargs):
				with print_messages():
					return await func(*args, **kwargs)
			# @wraps doesn't work on coros
			functools.update_wrapper(wrapped, func)
		else:
			@wraps(func)
			def wrapped(*args, **kwargs):
				with print_messages():
					return func(*args, **kwargs)
		return wrapped
	return wrapper

@bot.event
async def on_ready():
	global needed_guilds, guild_count

	print('Ready.')
	guild_count = 204
	await delete_guilds()
	needed_guilds = set()

	await create_guilds(prefix='EmoteBackend ', start=guild_count, limit=1, total=100)
	needed_guilds.update(bot.guilds)
	await update_permissions()
	await add_user_to_guilds()

@print_status('Deleting guilds')
async def delete_guilds():
	for guild in bot.guilds:
		await guild.delete()

def format_guild_name(n, max_n, prefix='EmoteBackend '):
	pad_length = len(str(max_n)) - 1
	# space out the number so that the icon for each guild in the sidebar shows the full number
	# e.g. 3 -> '0 3' if the limit is 100
	return prefix + ' '.join(str(n).zfill(pad_length))

@print_status('Creating guilds')
async def create_guilds(prefix, *, start, limit, total):
	"""create at most `limit` guilds named with numbers starting at `start`"""

	pad_length = len(str(total)) - 1

	for i in range(start, start + limit):
		try:
			guild = await bot.create_guild(format_guild_name(i, total, prefix=prefix))
		except discord.HTTPException:
			return
		global guild_count
		guild_count += 1
		needed_guilds.add(guild)

async def clear_guild(guild):
	# By default, discord creates 4 channels to make it easy for users:
	# A "text channels" category, a "voice channels" category,
	# a voice channel and a text channel. We want none of those.
	# There is also an invite created for the text channel, but that's deleted when the channel dies.
	for channel in guild.channels:
		await channel.delete()

administrator = discord.Permissions()
administrator.administrator = True

@print_status('Updating permissions')
async def update_permissions():
	for guild in bot.guilds:
		default_role = guild.default_role
		default_role.permissions.mention_everyone = False
		await default_role.edit(permissions=default_role.permissions)

async def add_user_to_guilds():
	guild = get_needed_guild()

	ch = await guild.create_text_channel('foo')
	print(await ch.create_invite())
	needed_permissions = discord.Permissions()
	needed_permissions.administrator = True
	print(discord.utils.oauth_url(bot_user_id, permissions=needed_permissions, guild=guild))

def get_needed_guild():
	try:
		return next(iter(needed_guilds))
	except StopIteration:
		raise ValueError('no more guilds') from None

@bot.event
async def on_member_join(member):
	global guild_count
	guild = member.guild
	needed_guilds.remove(guild)
	await clear_guild(guild)
	await guild.edit(owner=member)
	await guild.leave()
	await create_guilds('EmoteBackend ', start=guild_count, limit=1, total=100)
	guild_count += 1
	await add_user_to_guilds()

def usage() -> typing.NoReturn:
	print('Usage:', sys.argv[0], '<guild creator bot token> <Emote Collector user ID>', file=sys.stderr)
	sys.exit(1)

def main():
	global bot_user_id
	if len(sys.argv) > 2:
		token = sys.argv[1]
		bot_user_id = sys.argv[2]
	else:
		usage()

	bot.run(token)

if __name__ == '__main__':
	main()
