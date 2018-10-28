#!/usr/bin/env python3
# encoding: utf-8

import io

import discord

from .. import utils
from ..utils import custom_send

# it's not exactly 8MiB because
# the limit is not on the file size but on the whole request
FILE_SIZE_LIMIT = 8 * 1024 ** 2 - 512

async def upload_to_privatebin_if_too_long(original_send, content=None, **kwargs):
	if content is None:
		return True,

	content = str(content)
	if len(content) <= 2000:
		return True,

	out = io.StringIO(content)
	if utils.size(out) > FILE_SIZE_LIMIT:
		# translator's note: this is sent to the user when the bot tries to send a message larger than ~8MiB
		return False, await original_send(_('Way too long.'))

	file = discord.File(fp=io.StringIO(content), filename='message.txt')
	# translator's note: this is sent to the user when the bot tries to send a message >2000 characters
	# but less than 8MiB
	return False, await original_send(_('Way too long. Message attached.'), **kwargs, file=file)

def setup(bot):
	custom_send.register(upload_to_privatebin_if_too_long)

def teardown(bot):
	custom_send.unregister(upload_to_private_bin_if_too_long)
