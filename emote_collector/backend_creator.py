#!/usr/bin/env python3

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

import os
import sys
import time
import typing
import asyncio
import inspect
import logging
import functools
import contextlib
import webbrowser

import discord

logging.getLogger('discord').setLevel(logging.ERROR)

GUILD_NAME_PREFIX = 'EmoteBackend '
GUILDS_TO_CREATE = 100

bot = discord.Client()

@bot.event
async def on_ready():
	global guild_count

	await delete_guilds()

	first_guild = await create_guild()
	await update_permissions()

	print('You will have to fill out a lot of CAPTCHAs, so it is recommended to install the Buster captcha solver.')
	print('For Firefox: https://addons.mozilla.org/en-US/firefox/addon/buster-captcha-solver/')
	print('For Chrome: https://chrome.google.com/webstore/detail/buster-captcha-solver-for/mpbjkejclgfgadiemmefgebjfooflfhl')
	print("I also needed to install the user input simulation, which you can install by enabling it in the extension's settings.")
	print("If you can't or don't want to install the add-on, you should still do the audio CAPTCHAs, as they're way easier.")

	await add_user_to_guild(first_guild)

async def delete_guilds():
	for guild in bot.guilds:
		with contextlib.suppress(discord.HTTPException):
			await guild.delete()

def format_guild_name(n):
	pad_length = len(str(GUILDS_TO_CREATE)) - 1
	# space out the number so that the icon for each guild in the sidebar shows the full number
	# e.g. 3 -> '0 3' if the limit is 100
	return GUILD_NAME_PREFIX + ' '.join(str(n).zfill(pad_length))

async def create_guild():
	global guild_count
	try:
		guild = await bot.create_guild(format_guild_name(guild_count))
	except discord.HTTPException:
		return
	guild_count += 1
	return guild

async def clear_guild(guild):
	# By default, discord creates 4 channels to make it easy for users:
	# A "text channels" category, a "voice channels" category,
	# a voice channel and a text channel. We want none of those.
	# There is also an invite created for the text channel, but that's deleted when the channel dies.
	for channel in guild.channels:
		await channel.delete()

administrator = discord.Permissions()
administrator.administrator = True

async def update_permissions():
	for guild in bot.guilds:
		default_role = guild.default_role
		default_role.permissions.mention_everyone = False
		with contextlib.suppress(discord.HTTPException):
			await default_role.edit(permissions=default_role.permissions)

async def add_user_to_guild(guild):
	ch = await guild.create_text_channel('foo')
	invite = (await ch.create_invite()).url
	webbrowser.open(invite)

def add_bot_to_guild(guild):
	needed_permissions = discord.Permissions()
	needed_permissions.administrator = True
	url = discord.utils.oauth_url(bot_user_id, permissions=needed_permissions, guild=guild)
	webbrowser.open(url)

@bot.event
async def on_member_join(member):
	guild = member.guild

	if member == bot.user:
		return

	if member.id != bot_user_id:
		await clear_guild(guild)
		await guild.edit(owner=member)
		add_bot_to_guild(guild)
	else:
		await guild.leave()
		if guild_count > original_guild_count and guild_count % GUILDS_TO_CREATE == 0:
			await bot.close()
			return

		guild = await create_guild()
		await add_user_to_guild(guild)

def usage():
	print(
		'Usage:', sys.argv[0],
		'<guild creator bot token> <Emote Collector user ID> [existing backend guild count]',
		file=sys.stderr)

def main():
	global bot_user_id, guild_count, original_guild_count

	if len(sys.argv) == 1:
		usage()
		sys.exit(1)
	if len(sys.argv) == 2:
		usage()
		sys.exit(1)
	token = sys.argv[1]
	bot_user_id = int(sys.argv[2])
	if len(sys.argv) > 3:
		guild_count = original_guild_count = int(sys.argv[3])

	bot.run(token)

if __name__ == '__main__':
	main()
