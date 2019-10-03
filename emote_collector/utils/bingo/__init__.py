# SPDX-License-Identifier: BlueOak-1.0.0

import asyncio
import base64
import collections
import functools
import io
import itertools
import json
import random
import operator
import os
import sys
import textwrap
from pathlib import Path

import aiohttp

from ... import BASE_DIR
from ... import utils
from .board import *

COORDS = {
	c: [(x, y) for y in (327, 592, 857, 1121, 1387)]
	for c, x in zip('BINGO', (284, 548, 813, 1078, 1342))}
COORDS['N'][2] = None

# width and height (within the border) of one square
SQUARE_SIZE = 256

DATA_DIR = BASE_DIR / 'data' / 'bingo'

def marshal(board):
	return board.value, board.categories.items, board.marks.items

def draw_board(img, cats):
	from wand.drawing import Drawing

	with Drawing() as draw:
		draw.font = str(DATA_DIR / 'DejaVuSans.ttf')
		draw.font_size = 40
		for (col, row), cat in cats:
			try:
				x, y = COORDS[col][row - 1]
			except IndexError:
				print(col, row)
				raise
			draw.text(x, y, '\n'.join(textwrap.wrap(cat, 10)))
		draw(img)

def render(board):
	from wand.image import Image
	from wand.drawing import Drawing

	with Image(filename=DATA_DIR / 'bingo_board_base.png') as img:
		draw_board(img, board.categories)
		with Drawing() as draw:
			draw_marks(draw, img, ((point, base64.b64decode(img.encode('ascii'))) for point, (*_, img) in board.marks))
			draw(img)

		return img.make_blob(format='png')

def draw_marks(draw, img, marks):
	from wand.image import Image

	for (col, row), eimg in marks:
		left, top = COORDS[col][row - 1]

		half = SQUARE_SIZE // 2
		with Image(blob=eimg) as eimg:
			eimg.transform(resize=f'{half}x{half}')
			draw.composite(
				operator='over',
				left=left+half-65, top=top+25,
				width=eimg.width, height=eimg.height,
				image=eimg)

async def download_all(bot, urls):
	sess = bot.cogs['Emotes'].http
	async def read(url):
		async with sess.get(url, raise_for_status=True) as resp:
			return url, await resp.read()
	tasks = (
		bot.loop.create_task(read(url))
		for url in urls)
	return await utils.gather_or_cancel(*tasks)

async def render_in_subprocess(bot, board):
	url_index = collections.defaultdict(list)
	for i, e in enumerate(board.marks.items):
		if e is None:
			continue
		nsfw, name, id, animated = e
		url_index[utils.emote.url(id, animated=animated)].append(i)

	images = await download_all(bot, url_index)
	marks = board.marks.items[:]
	for url, image in images:
		for i in url_index[url]:
			marks[i] += (base64.b64encode(image).decode('ascii'),)
	del images

	proc = await asyncio.create_subprocess_exec(
		# see __main__.py
		sys.executable, '-m', __name__,

		stdin=asyncio.subprocess.PIPE,
		stdout=asyncio.subprocess.PIPE,
		stderr=asyncio.subprocess.PIPE)

	image_data, err = await proc.communicate(json.dumps({
		'value': board.value,
		'categories': board.categories.items,
		'marks': marks}).encode())

	if proc.returncode != 0:
		raise RuntimeError(err.decode('utf-8') + f'Return code: {proc.returncode}')

	return image_data
