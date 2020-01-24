# SPDX-License-Identifier: BlueOak-1.0.0

import itertools

from discord.ext import commands

__all__ = ('BingoBoard', 'index', 'EmoteCollectorBingoBoard')

class BingoBoard:
	WIDTH = 5
	HEIGHT = 5

	SIZE = HEIGHT * WIDTH
	SQUARES = SIZE - 1  # free space

	COL_I = {c: i for i, c in enumerate('BINGO')}
	COL_NAMES = {i: c for c, i in COL_I.items()}

	FREE_SPACE_I = HEIGHT * COL_I['N'] + 2

	def __init__(self, *, value=None):
		self.value = 0 if value is None else value
		self['N', 3] = 1  # free space

	reset = __init__

	def is_playable(self, col, row):
		"""return whether the square has room"""
		return self[col, row] == 0

	def has_won(self):
		board = self.value

		horiz_mask = self.HORIZ_MASK
		for _ in range(self.HEIGHT):
			if board & horiz_mask == horiz_mask:
				return True
			horiz_mask <<= 1

		vert_mask = self.VERT_MASK
		for _ in range(self.WIDTH):
			if board & vert_mask == vert_mask:
				return True
			vert_mask <<= self.HEIGHT

		if board & self.DIAGONAL_TOP_LEFT == self.DIAGONAL_TOP_LEFT:
			return True
		if board & self.DIAGONAL_BOTTOM_LEFT == self.DIAGONAL_BOTTOM_LEFT:
			return True

		return False

	def __setitem__(self, pos, value):
		mask = self.mask(pos)
		if value:
			self.value |= mask
		else:
			self.value &= ~mask

	def __getitem__(self, pos):
		mask = self.mask(pos)
		return self.value & mask != 0

	@classmethod
	def parse_pos(cls, pos):
		col, row = pos
		try:
			col, row = cls.COL_I[col], int(row) - 1
		except (KeyError, IndexError):
			raise commands.BadArgument(_('Invalid position.'))
		return col, row

	@classmethod
	def index(cls, pos):
		col, row = cls.parse_pos(pos)
		return col * cls.HEIGHT + row

	@classmethod
	def mask(cls, pos):
		return 1 << cls.index(pos)

	@classmethod
	def skip_free_space(cls, items):
		"""given a list SQUARES items long, return a list SIZE items long with a blank free space"""
		# set free space to None
		items.append(items[cls.FREE_SPACE_I])
		items[cls.FREE_SPACE_I] = None
		return items

	def __str__(self):
		from io import StringIO
		buf = StringIO()

		buf.write('  ')
		for w in range(self.WIDTH):
			# column indexes
			buf.write(self.COL_NAMES[w])
			buf.write(' ')

		buf.write('\n')

		for h in range(1, self.HEIGHT + 1):
			buf.write(str(h))
			for w in 'BINGO':
				buf.write(' ')
				buf.write('X' if self[w, h] else '.')
			if h != self.HEIGHT:  # skip writing the newline at the end
				buf.write('\n')

		return buf.getvalue()

	@classmethod
	def _init_masks(cls):
		import functools
		import operator

		positions = list(itertools.product('BINGO', range(1, 6)))
		masks = {pos: cls.mask(pos) for pos in positions}

		bit_or = functools.partial(functools.reduce, operator.or_)

		cls.HORIZ_MASK = bit_or(masks[col, 1] for col in 'BINGO')
		cls.VERT_MASK = bit_or(masks['B', i] for i in range(1, 6))

		cls.DIAGONAL_TOP_LEFT = bit_or(masks['BINGO'[i - 1], i] for i in range(1, 6))
		cls.DIAGONAL_BOTTOM_LEFT = bit_or(masks['BINGO'[5 - i], i] for i in range(1, 6)[::-1])

BingoBoard._init_masks()

class BingoItemWrapper:
	def __init__(self, cls, *, items=None):
		self.cls = cls
		items = [None] * cls.SQUARES if items is None else items
		self.items = cls.skip_free_space(items)

	def index(self, pos):
		col, row = pos
		row = int(row)
		if col == 'N' and row == 3:
			raise commands.BadArgument(_('Position may not be the free space.'))
		col, row = self.cls.COL_I[col], row - 1
		i = self.cls.HEIGHT * col + row
		return i

	def __getitem__(self, pos):
		return self.items[self.index(pos)]

	def __setitem__(self, pos, value):
		self.items[self.index(pos)] = value

	def __delitem__(self, pos):
		self.items[self.index(pos)] = None

	def __iter__(self):
		for pos in itertools.product(self.cls.COL_I, range(1, self.cls.HEIGHT + 1)):
			if pos == ('N', 3):
				continue
			value = self[pos]
			if value is not None:
				yield pos, value

index = BingoItemWrapper(BingoBoard).index

class EmoteCollectorBingoBoard(BingoBoard):
	def __init__(self, *, value=None, categories=None, marks=None):
		super().__init__(value=value)
		self.categories = BingoItemWrapper(type(self), items=categories)
		self.marks = BingoItemWrapper(type(self), items=marks)

	def is_nsfw(self):
		return any(nsfw != 'SFW' for nsfw, name, id, image in filter(None, self.marks.items))
