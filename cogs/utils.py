#!/usr/bin/env python3
# encoding: utf-8

"""
Various utilities for use in discord.py bots.

Constants:

SUCCESS_EMOTES -- index it with True or False to get an emote indicating success or failure.

Classes:

EmojiConnoisseurContext: a generic context which extends discord.ext.commands.Context.
LRUDict: an extension of lru.LRU to add a pop method, and support kwargs for the update method.

Functions:

typing: a decorator for discord.py commmands that sends a typing indicator to the invoking channel
until the command returns.
fix_first_line: takes in a list of lines and returns a fixed multi line message for compact mode users
create_gist: uploads text to gist.github.com
emote_url: given an ID of an emote, get the url which points to that emote's image
format_time: formats a datetime object to look like my preferred format
strip_angle_brackets: <http://foo.example> -> http://foo.example
"""


import asyncio as _asyncio
from datetime import datetime as _datetime
import json as _json
import logging as _logging

from aiohttp import ClientSession as _ClientSession
import discord as _discord
from discord.ext import commands as _commands


_logger = _logging.getLogger('utils')  # i really need to start using __all__...


class Utils:
	def __init__(self, bot):
		self.bot = bot
		self.http_session = _ClientSession(loop=bot.loop)

	def __unload(self):
		self.http_session.close()

	"""Emotes used to indicate success/failure. You can obtain these from the discordbots.org guild,
	but I uploaded them to my test server
	so that both the staging and the stable versions of the bot can use them"""
	SUCCESS_EMOTES = ('<:tickNo:416845770239508512>', '<:tickYes:416845760810844160>')

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

	async def create_gist(self, filename, contents: str, *, description=None):
		"""Upload a single file to Github Gist. Multiple files Never™"""
		_logger.debug('Attempting to post %s to Gist', filename)

		data = {
			'public': False,
			'files': {
				filename: {
					'content': contents}}}

		if description is not None:
			data['description'] = description

		async with self.http_session.post('https://api.github.com/gists', data=_json.dumps(data)) as resp:
			if resp.status == 201:
				return _json.loads(await resp.text())['html_url']

	@staticmethod
	def format_emote(emote):
		"""Format an emote for use in messages."""
		return f"<{'a' if emote['animated'] else ''}:{emote['name']}:{emote['id']}>"

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
