#!/usr/bin/env python3.6
# encoding: utf-8

"""a selfbot that creates guilds"""

import asyncio
import base64
from functools import wraps
import json
import os
import sys
import time

import discord
import gi
gi.require_version('Notify', '0.7')  # warnings if I don't do this ¯\_(ツ)_/¯
from gi.repository import Notify
import selenium.webdriver
from selenium.common.exceptions import NoSuchElementException


bot = discord.Client(self_bot=True)
Notify.init(__name__)


def print_status(status_message, synchronous=False):
	def wrapper(func):
		if asyncio.iscoroutinefunction(func):
			# @wraps doesn't work on coros
			async def wrapped(*args, **kwargs):
				print('\n' + status_message + '...', end=' ')
				result = await func(*args, **kwargs)
				print('done.', end='')
				return result
		else:
			@wraps(func)
			def wrapped(*args, **kwargs):
				print('\n' + status_message + '...', end=' ')
				result = func(*args, **kwargs)
				print('done.', end='')
				return result
		return wrapped
	return wrapper


@bot.event
async def on_ready():
	print('Ready.')
	await wipe_guilds()
	await create_guilds(prefix='EmojiBackend ', limit=100)
	await clear_guilds()
	# await rename_guilds()
	add_bot_to_guilds()
	await bot.logout()
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
	for guild in bot.guilds:
		await guild.edit(name=guild.name.replace('Emoji Backend', 'EmojiBackend'))  # example


@print_status('Adding bot to guilds. This will require your input', synchronous=True)
def add_bot_to_guilds():
	# these are the guilds which do not have the bot in them yet
	pending_guilds = [guild for guild in bot.guilds if guild.member_count == 1]

	driver = selenium.webdriver.Firefox()

	perms = discord.Permissions()
	perms.manage_emojis = True

	# XXX for older accounts, a bot's user ID
	# is not the same as its oauth client ID.
	# if that is your situation, adjust the code below
	client_id = token_id(get_token_from_config())
	oauth_url = discord.utils.oauth_url(client_id, perms)

	driver.get(oauth_url)

	notify('Waiting for you to log in')
	wait_for_url(driver, oauth_url)  # oauth URL redirects to login page if logged out

	for i, guild in enumerate(pending_guilds, 1):
		driver.get(oauth_url)

		add_guild(driver, guild)
		notify('{} guild{} down, {} to go!'.format(i, 's' if i > 1 else '', len(pending_guilds) - i))


def add_guild(driver, guild):
	# wait until the dropdown to choose a server appears
	wait_for_element(driver, 'select > option[value="{}"]'.format(guild.id)).click()
	wait_for_element(driver, 'button.primary').click()
	driver.switch_to.frame(wait_for_element(driver, 'iframe'))  # switch to the reCAPTCHA iframe
	# click "i am not a robot"
	wait_for_element(driver, '.recaptcha-checkbox-checkmark').click()
	driver.switch_to.default_content()  # switch back out
	# wait until the user completes the CAPTCHA and auth is finished
	wait_for_url(driver, 'https://discordapp.com/oauth2/authorized')


def get_token_from_config():
	with open('data/config.json') as f:
		return json.load(f)['token']


def token_id(token) -> int:
	"""decodes a token to retrieve the user ID"""
	return int(base64.b64decode(token.split('.')[0]))


def wait_for_element(driver, css_selector, delay=0.25):
	while True:
		try:
			return driver.find_element_by_css_selector(css_selector)
		except NoSuchElementException:
			time.sleep(delay)
			continue


def wait_for_url(driver, url, delay=0.25):
	while driver.current_url != url:
		time.sleep(delay)


def notify(message):
	Notify.Notification.new(message).show()


def usage():
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
