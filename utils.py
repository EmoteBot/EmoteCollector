#!/usr/bin/env python3
# encoding: utf-8

from functools import wraps as _wraps
import json as _json

from aiohttp import ClientSession as _ClientSession
from discord.ext import commands


session = _ClientSession()


def pop(d, key, default=None):
	"""Needed for LRUDicts, which cannot be extended because lru-dict is written in C."""
	if default is None and key not in d:
		raise KeyError(key)
	result = d[key]
	del d[key]
	return result


def typing(func):
	"""Makes a command function run with the context.typing() decorator.
	This will make the bot appear to be typing for until the command returns.
	While you can just wrap your entire code in `async with context.typing()`,
	this isn't ideal if you already have a lot of indents or a long function.
	Also, context.trigger_typing() works but only for 10 seconds.
	"""
	@_wraps(func)
	async def wrapped(*args, **kwargs):
		# if func is a method, args starts with self, context, ...
		# otherwise args starts with context, ...
		context = args[0] if isinstance(args[0], commands.Context) else args[1]
		async with context.typing():
			await func(*args, **kwargs)
	return wrapped


async def create_gist(filename, contents: str):
	"""Upload a single file to Github Gist. Multiple files Never™"""
	async with session.post(
		'https://api.github.com/gists',
		data=_json.dumps({
			'public': False,
			'files': {
				filename: {
					'content': contents}}})) as resp:
		if resp.status == 201:
			return _json.loads(await resp.text())['html_url']
