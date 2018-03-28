#!/usr/bin/env python3.6
# encoding: utf-8

"""
Various utilities for use in discord.py bots.

Constants:

SUCCESS_EMOTES -- index it with True or False to get an emote indicating success or failure.

Classes:

EmojiConnoisseurContext: a generic context which extends discord.ext.commands.Context.
LRUDict: an extension of lru.LRU to add a pop method, and support kwargs for the update method.
Utils: a cog which wraps up most of the functions listed below

Functions:

get_message: gets a message in a channel by negative index, like lists
fix_first_line: takes in a list of lines and returns a fixed multi line message for compact mode users
create_gist: uploads text to gist.github.com
format_user: formats a discord.py User object for human readable display
format_time: formats a datetime object to look like my preferred format
strip_angle_brackets: <http://foo.example> -> http://foo.example
"""


import asyncio as _asyncio
from datetime import datetime as _datetime
import functools as _functools
from github3 import GitHub as _GitHub
from github3.exceptions import GitHubError as _GitHubError
import json as _json
import logging as _logging

import discord as _discord
from discord.ext import commands as _commands


_logger = _logging.getLogger('utils')
_logger.setLevel(_logging.DEBUG)


class Utils:
	def __init__(self, bot):
		self.bot = bot
		self.converter = _commands.clean_content(use_nicknames=False, escape_markdown=True)
		self.github = _GitHub(token=self.bot.config['tokens']['github'])

	"""Emotes used to indicate success/failure. You can obtain these from the discordbots.org guild,
	but I uploaded them to my test server
	so that both the staging and the stable versions of the bot can use them"""
	SUCCESS_EMOTES = ('<:tickNo:416845770239508512>', '<:tickYes:416845760810844160>')

	async def codeblock(self, context, message, *, lang=''):
		cleaned = await self.converter.convert(context, str(message))
		return f'```{lang}\n{cleaned}```'

	@staticmethod
	async def get_message(channel, index: int) -> _discord.Message:
		"""Gets channel[-index]. For instance get_message(channel, -2) == second to last message.
		Requires channel history permissions"""
		return await channel.history(limit=-index, reverse=True).next()

	@staticmethod
	def fix_first_line(lines: list) -> str:
		"""In compact mode, prevent the first line from being misaligned because of the bot's username"""
		if len(lines) > 1:
			lines[0] = '\N{zero width space}\n' + lines[0]
		return '\n'.join(lines)

	async def create_gist(self, filename, content: str, *, description=''):
		"""Upload a single file to Github Gist. Multiple files Never™
		This does not currently work since GitHub disabled anonymous gist creation."""

		_logger.debug('Attempting to post %s to Gist', filename)
		create_function = _functools.partial(self.github.create_gist,
			description=description,
			files={filename: {'content': content}},
			public=False)
		try:
			gist = await self.bot.loop.run_in_executor(None, create_function)
		except _GitHubError as ex:
			_logging.error('gist error:')
			_logging.error(ex.response.content)
			raise
		else:
			return gist.html_url

	def format_user(self, id, *, mention=False):
		"""Format a user ID for human readable display."""
		user = self.bot.get_user(id)
		if user is None:
			return f'Unknown user with ID {id}'
		# not mention: @null byte#8191 (140516693242937345)
		# mention: <@140516693242937345> (null byte#8191)
		# this allows people to still see the username and discrim
		# if they don't share a server with that user
		return f'{user.mention if mention else user} ({user if mention else user.id})'

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


def setup(bot):
	bot.add_cog(Utils(bot))
