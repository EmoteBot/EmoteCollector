#!/usr/bin/env python3
# encoding: utf-8

"""
privatebin.py: uploads text to privatebin
https://gist.github.com/e96393c533464840b5a45fbba708b058

using code from <https://github.com/r4sas/PBinCLI/blob/master/pbincli/actions.py>,
© 2017–2018 R4SAS <r4sas@i2pmail.org>
using code from <https://github.com/khazhyk/dango.py/blob/master/dango/zerobin.py>,
© 2017 khazhyk
"""

import asyncio
import base64
import json
import os
import sys
import zlib

import aiohttp
from sjcl import SJCL


def encrypt(text):
	key = base64.urlsafe_b64encode(os.urandom(32))
	# Encrypting text
	encrypted_data = SJCL().encrypt(compress(text.encode('utf-8')), key, mode='gcm')
	return encrypted_data, key

def compress(s: bytes):
	co = zlib.compressobj(wbits=-zlib.MAX_WBITS)
	b = co.compress(s) + co.flush()

	return base64.b64encode(''.join(map(chr, b)).encode('utf-8'))

def make_payload(text):
	# Formatting request
	request = dict(
		expire='never',
		formatter='plaintext',
		burnafterreading='0',
		opendiscussion='0',
	)

	cipher, key = encrypt(text)
	# TODO: should be implemented in upstream
	for k in ['salt', 'iv', 'ct']: cipher[k] = cipher[k].decode()

	request['data'] = json.dumps(cipher, ensure_ascii=False, indent=None, default=lambda x: x.decode('utf-8'))
	return request, key

lock = asyncio.Lock()

class PrivateBinError(Exception): pass

async def upload(text, loop=None):
	loop = loop or asyncio.get_event_loop()

	await lock.acquire()
	result = None
	payload, key = await loop.run_in_executor(None, make_payload, text)
	python_version = '.'.join(map(str, sys.version_info[:3]))
	async with aiohttp.ClientSession(headers={
		'User-Agent': 'privatebin.py/0.0.3 aiohttp/%s python/%s' % (aiohttp.__version__, python_version),
		'X-Requested-With': 'JSONHttpRequest'
	}) as session:
		for tries in range(2):
			async with session.post('https://privatebin.net/', data=payload) as resp:
				resp_json = await resp.json()
				if resp_json['status'] == 0:
					result = url(resp_json['id'], key)
					break
				elif resp_json['status'] == 1:  # rate limited
					await asyncio.sleep(5)

	lock.release()

	if result is None:
		raise PrivateBinError('Failed to upload to privatebin')
	else:
		return result

def url(paste_id, key):
	return 'https://privatebin.net/?%s#%s' % (paste_id, key.decode('utf-8'))

if __name__ == '__main__':
	loop = asyncio.get_event_loop()

	print(loop.run_until_complete(upload(sys.stdin.read())))
