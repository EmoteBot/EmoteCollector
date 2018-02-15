#!/usr/bin/env python3
# encoding: utf-8

from functools import wraps as _wraps
import json as _json
import sys as _sys

from aiohttp import ClientSession as _ClientSession


"""More owners, other than Emoji Backend 0. If more backend accounts are needed, add them here."""
EXTRA_OWNERS = (140516693242937345,)
session = _ClientSession()


async def is_owner(context):
	user = context.author
	return user.id in EXTRA_OWNERS or await context.bot.is_owner(user)


def typing(func):
	@_wraps(func)
	async def wrapped(self, context, *args, **kwargs):
		async with context.typing():
			await func(self, context, *args, **kwargs)
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


def log(*args, **kwargs):
	kwargs['file'] = _sys.stderr
	print(*args, **kwargs)
