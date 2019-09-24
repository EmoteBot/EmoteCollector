# SPDX-License-Identifier: BlueOak-1.0.0

import asyncio
import base64
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
from .board import EmoteCollectorBingoBoard
from ..image import scale_resolution

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
			eimg.resize(*scale_resolution((img.width, img.height), (half, half)))
			draw.composite(
				operator='over',
				left=left+half-65, top=top+25,
				width=eimg.width, height=eimg.height,
				image=eimg)

async def mark(bot, board, pos, emote):
	sess = bot.cogs['Emotes'].http
	async with sess.get(emote.url) as resp:
		eimg = base64.b64encode(await resp.read()).decode('ascii')

	board[pos] = 1
	board.marks[pos] = emote.is_nsfwf(), emote.name, emote.id, eimg

def remove_mark(board, pos):
	board[pos] = 0
	del board.marks[pos]

def new():
	with open(DATA_DIR / "bingo_categories.txt") as f:
		cats = list(map(str.rstrip, f))
	random.shuffle(cats)

	categories = cats[:EmoteCollectorBingoBoard.SQUARES]
	return EmoteCollectorBingoBoard(categories=categories)

async def render_in_subprocess(board):
	proc = await asyncio.create_subprocess_exec(
		# see __main__.py
		sys.executable, '-m', __name__,

		stdin=asyncio.subprocess.PIPE,
		stdout=asyncio.subprocess.PIPE,
		stderr=asyncio.subprocess.PIPE)

	image_data, err = await proc.communicate(json.dumps({
		'value': board.value,
		'categories': board.categories.items,
		'marks': board.marks.items}).encode())

	if proc.returncode != 0:
		raise RuntimeError(err.decode('utf-8') + f'Return code: {proc.returncode}')

	return image_data
