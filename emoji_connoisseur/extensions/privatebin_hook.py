#!/usr/bin/env python3
# encoding: utf-8

import io

import discord

from ..utils import custom_send
from ..utils import privatebin

async def upload_to_privatebin_if_too_long(original_send, content=None, **kwargs):
	if content is None:
		return True,

	content = str(content)
	if len(content) <= 2000:
		return True,

	try:
		url = await privatebin.upload(content)
	except privatebin.PrivateBinError:
		file = discord.File(fp=io.StringIO(content), filename='message.txt')
		return False, await original_send(_('Way too long. Message attached.'), **kwargs, file=file)

	return False, await original_send(
		_('Way too long. Uploaded to PrivateBin: {url}').format(**locals()), **kwargs)

def setup(bot):
	custom_send.register(upload_to_privatebin_if_too_long)

def teardown(bot):
	custom_send.restore()
