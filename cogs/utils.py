#!/usr/bin/env python3.6
# encoding: utf-8

"""
Various utilities for use in discord.py bots.
"""


import asyncio as _asyncio
from datetime import datetime as _datetime
import discord as _discord
import functools as _functools
import json as _json
import logging as _logging
import os.path
import urllib.parse

import discord as _discord
from discord.ext import commands as _commands


_logger = _logging.getLogger('utils')


class Utils:
	def __init__(self, bot):
		self.bot = bot

	"""Emotes used to indicate success/failure. You can obtain these from the discordbots.org guild,
	but I uploaded them to my test server
	so that both the staging and the stable versions of the bot can use them"""
	SUCCESS_EMOTES = ('<:error:416845770239508512>', '<:success:416845760810844160>')

	async def codeblock(self, message, *, lang=''):
		cleaned = message.replace('```', '\N{zero width space}'.join('```'))
		return f'```{lang}\n{cleaned}```'

	@staticmethod
	async def get_message(channel, index: int) -> _discord.Message:
		"""Gets channel[-index]. For instance get_message(channel, -2) == second to last message.
		Requires channel history permissions"""
		return await channel.history(limit=-index, reverse=True).next()

	@staticmethod
	def fix_first_line(message: str) -> str:
		"""In compact mode, prevent the first line from being misaligned because of the bot's username"""
		if '\n' in message:
			message = '\N{zero width space}\n' + message
		return message

	@staticmethod
	def emote_info(url):
		"""Return a two tuple (id, animated) for the given emote url"""
		path = urllib.parse.urlparse(url).path
		filename, extension = os.path.splitext(os.path.basename(path))
		return int(filename), extension == '.gif'

	def format_user(self, id, *, mention=False):
		"""Format a user ID for human readable display."""
		user = self.bot.get_user(id)
		if user is None:
			return f'Unknown user with ID {id}'
		# not mention: @null byte#8191 (140516693242937345)
		# mention: <@140516693242937345> (null byte#8191)
		# this allows people to still see the username and discrim
		# if they don't share a server with that user
		if mention:
			return f'{user.mention} (@{user})'
		else:
			return f'@{user} ({user.id})'

	@staticmethod
	def format_time(date: _datetime):
		"""Format a datetime to look like '2018-02-22 22:38:12 UTC'."""
		return date.strftime('%Y-%m-%d %H:%m:%S %Z')

	@staticmethod
	def strip_angle_brackets(string):
		"""Strip leading < and trailing > from a string.
		Useful if a user sends you a url like <this> to avoid embeds, or to convert emotes to reactions."""
		if string.startswith('<') and string.endswith('>'):
			return string[1:-1]
		return string

	@staticmethod
	def format_http_exception(exception: _discord.HTTPException):
		"""Formats a discord.HTTPException for relaying to the user.
		Sample return value:

		BAD REQUEST (status code: 400):
		Invalid Form Body
		In image: File cannot be larger than 256 kb.
		"""
		return (
			f'{exception.response.reason} (status code: {exception.response.status}):'
			f'\n{exception.text}')


def setup(bot):
	bot.add_cog(Utils(bot))
