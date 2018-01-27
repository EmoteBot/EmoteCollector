#!/usr/bin/env python3
# encoding: utf-8

"""a selfbot that creates guilds"""

from functools import wraps
import sys
import time

import discord
import gi
gi.require_version('Notify', '0.7') # warnings if I don't do this ¯⧹_(ツ)_⧸¯
from gi.repository import Notify
import selenium.webdriver
from selenium.common.exceptions import NoSuchElementException

from bot import EmojiConnoisseur

bot = discord.Client(self_bot=True)
connoisseur = EmojiConnoisseur()
Notify.init(__name__)


def print_status(status_message, synchronous=False):
	def wrapper(func):
		if synchronous:
			@wraps(func)
			def wrapped(*args, **kwargs):
				print('\n' + status_message + '...', end=' ')
				result = func(*args, **kwargs)
				print('done.')
				return result
		else:
			@wraps(func)
			async def wrapped(*args, **kwargs):
				print('\n' + status_message + '...', end=' ')
				result = await func(*args, **kwargs)
				print('done.')
				return result
		return wrapped
	return wrapper


@bot.event
async def on_ready():
	print('Ready.')
	#await wipe_guilds()
	#await create_guilds(prefix='Emoji Backend ', limit=100)
	#await clear_guilds()
	#await rename_guilds()
	add_bot_to_guilds()
	#await bot.logout()
	return


@print_status('Wiping guilds')
async def wipe_guilds():
	for guild in bot.guilds:
		await guild.delete()


@print_status('Creating guilds')
async def create_guilds(prefix, start=0, limit=50):
	"""create at most `limit` guilds named with numbers starting at `start`"""

	for i in range(start, limit):
		await bot.create_guild(prefix + str(i))


@print_status('Clearing guilds')
async def clear_guilds():
	for guild in bot.guilds:
		# By default, discord creates 4 channels to make it easy for users:
		# A "text channels" category, a "voice channels" category,
		# a voice channel and a text channel. We want none of those.
		for channel in guild.channels:
			await channel.delete()
		for invite in await guild.invites():
			await invite.delete()


@print_status('Renaming guilds')
async def rename_guilds():
	for guild in bot.guilds:
		await guild.edit(name=guild.name.replace('Emoji', 'EmojiBackend'))


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


@print_status('Adding bot to guilds. This will require your input', synchronous=True)
def add_bot_to_guilds():
	driver = selenium.webdriver.Firefox()
	perms = discord.Permissions.none()
	perms.manage_emojis = True
	oauth_url =	discord.utils.oauth_url(connoisseur.client_id, perms)
	driver.get(oauth_url)

	notify('Waiting for you to log in')
	wait_for_url(driver, oauth_url) # oauth URL redirects to login page if logged out

	for i, guild in enumerate(bot.guilds, 1):
		driver.get(oauth_url)

		wait_for_element(driver, 'select > option[value="{}"]'.format(guild.id)).click()
		wait_for_element(driver, 'button.primary').click()
		driver.switch_to.frame(wait_for_element(driver, 'iframe')) # switch to the reCAPTCHA iframe
		wait_for_element(driver, '.recaptcha-checkbox-checkmark').click()
		driver.switch_to.default_content() # switch back out
		wait_for_url(driver, 'https://discordapp.com/oauth2/authorized')
		notify('{} guild{} down, {} to go!'.format(i, 's' if i > 1 else '', len(bot.guilds) - i))


def notify(message):
	Notify.Notification.new(message).show()


def main():
	import os
	import sys

	try:
		bot.run(os.getenv('token', sys.argv[1]), bot=False)
	except IndexError:
		print('Usage:', sys.argv[0], '<token>', file=sys.stderr)
		print('You can also set $token.')


if __name__ == '__main__':
	main()
