#!/usr/bin/env python3
# encoding: utf-8

"""a selfbot that creates guilds"""

import os
import sys
import time
import base64
import typing
import asyncio
import inspect

import discord

import utils


bot = discord.Client(self_bot=True)


def print_status(status_message):
	def wrapper(func):
		if inspect.iscoroutinefunction(func):
			# @wraps doesn't work on coros
			async def wrapped(*args, **kwargs):
				print(status_message + '...', end=' ', file=sys.stderr)
				result = await func(*args, **kwargs)
				print('done.', file=sys.stderr)
				return result
		else:
			@wraps(func)
			def wrapped(*args, **kwargs):
				print(status_message + '...', end=' ', file=sys.stderr)
				result = func(*args, **kwargs)
				print('done.', file=sys.stderr)
				return result
		return wrapped
	return wrapper


@bot.event
async def on_ready():
	print('Ready.')
	await wipe_guilds()
	await create_guilds(prefix='EmoteBackend ', limit=100)
	await clear_guilds()
	await rename_guilds()

	global needed_guilds
	bot.needed_guilds = {guild for guild in bot.guilds if len(guild.members) < 2}

	await add_bot_to_guilds()

	return


@print_status('Wiping guilds')
async def wipe_guilds():
	for guild in bot.guilds:
		await guild.delete()


@print_status('Creating guilds')
async def create_guilds(prefix, start=0, limit=100):
	"""create at most `limit` guilds named with numbers starting at `start`"""

	pad_length = len(str(limit)) - 1

	for i in range(start, limit):
		# space out the number so that the icon for each guild in the sidebar shows the full number
		# e.g. 3 -> '0 3' if the limit is 100
		await bot.create_guild(prefix + ' '.join(str(i).zfill(pad_length)))


@print_status('Clearing default channels')
async def clear_guilds():
	for guild in bot.guilds:
		# By default, discord creates 4 channels to make it easy for users:
		# A "text channels" category, a "voice channels" category,
		# a voice channel and a text channel. We want none of those.
		# There is also an invite created for the text channel, but that's deleted when the channel dies.
		for channel in guild.channels:
			await channel.delete()


@print_status('Renaming guilds')
async def rename_guilds():
	for i, guild in enumerate(bot.guilds, 100):
		await guild.edit(name='EmojiBackend %s' % ' '.join(str(i)))


async def add_bot_to_guilds():
	try:
		next_guild = get_needed_guild()
	except ValueError:
		print(
			'Either all the backend guilds have been added to the bot,',
			'or you have not entered the user token correctly.',
			'Make sure that the user token you entered is the same one that owns all the backend guilds.')
		await bot.logout()
		return

	print('To add the bot to the backend guilds, use this link:')
	needed_permissions = discord.Permissions()
	needed_permissions.update(manage_emojis=True)
	print(discord.utils.oauth_url(get_bot_user_id(), needed_permissions))
	print('Then add the bot to this guild:', next_guild.name)


def get_needed_guild():
	try:
		return next(iter(bot.needed_guilds))
	except StopIteration:
		raise ValueError('no more guilds') from None


@bot.event
async def on_member_join(member):
	bot.needed_guilds.remove(member.guild)
	print(len(bot.guilds) - len(bot.needed_guilds), 'down,', len(bot.needed_guilds), 'to go.', end=' ')
	try:
		print('Now add', get_needed_guild().name, end='.\n')
	except ValueError:
		pass


def get_bot_user_id():
	return token_id(get_token_from_config())

def get_token_from_config():
	with open('data/config.py') as f:
		return utils.load_json_compat(f.read())['tokens']['discord']

def token_id(token) -> int:
	"""decodes a token to retrieve the user ID"""
	return int(base64.b64decode(token.split('.')[0]))


def usage() -> typing.NoReturn:
	print('Usage:', sys.argv[0], '<token>', file=sys.stderr)
	print('You can also set $token.', file=sys.stderr)
	sys.exit(1)


def main():
	if len(sys.argv) > 1:
		token = sys.argv[1]
	elif len(sys.argv) == 1:
		token = os.getenv('token')
		if token is None:
			usage()
	else:
		usage()

	bot.run(token, bot=False)


if __name__ == '__main__':
	main()
