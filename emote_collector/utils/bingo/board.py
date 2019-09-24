# SPDX-License-Identifier: BlueOak-1.0.0

import itertools

class BingoBoard:
	WIDTH = 5
	HEIGHT = 5

	H1 = HEIGHT + 1
	H2 = HEIGHT + 2
	SIZE = HEIGHT * WIDTH
	SIZE1 = H1 * WIDTH
	SQUARES = SIZE - 1  # free space

	COL_I = {c: i for i, c in enumerate('BINGO')}
	COL_NAMES = {i: c for c, i in COL_I.items()}
	FLIP_ROW = range(HEIGHT)[::-1]

	def __init__(self, *, value=None):
		self.value = 0 if value is None else value
		self['N', 3] = 1  # free space

	reset = __init__

	def is_playable(self, col, row):
		"""return whether the square has room"""
		return self[col, row] == 0

	def has_won(self):
		board = self.value
		y = board & (board >> self.HEIGHT)
		if (y & (y >> 2 * self.HEIGHT)) != 0:  # diagonal \
			return True
		y = board & (board >> self.H1)
		if (y & (y >> 2 * self.H1)) != 0:  # horizontal -
			return True
		y = board & (board >> self.H2)
		if (y & (y >> 2 * self.H2)) != 0:  # diagonal /
			return True
		y = board & (board >> 1)
		return (y & (y >> 2)) != 0  # vertical |

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
		col, row = cls.COL_I[col], cls.FLIP_ROW[row - 1]
		return col, row

	@classmethod
	def index(cls, pos):
		col, row = cls.parse_pos(pos)
		return col * cls.HEIGHT + row

	@classmethod
	def mask(cls, pos):
		col, row = cls.parse_pos(pos)
		return 1 << (col * cls.H1 + row)

	def __str__(self):
		from io import StringIO
		buf = StringIO()

		buf.write('  ')
		for w in range(self.WIDTH):
			# column indexes
			buf.write(self.COL_NAMES[w])
			buf.write(' ')

		buf.write('\n')

		for h in range(self.HEIGHT - 1, -1, -1):
			buf.write(str(self.HEIGHT - h))
			for w in range(h, self.SIZE1, self.H1):
				mask = 1 << w
				buf.write(' ')
				buf.write('X' if self.value & mask != 0 else '.')
			if h != 0:  # skip writing the newline at the end
				buf.write('\n')

		return buf.getvalue()

class BingoItemWrapper:
	def __init__(self, cls, *, items=None):
		self.cls = cls
		self.items = [None] * cls.SQUARES if items is None else items

	def index(self, pos):
		if pos == ('N', 3):
			raise ValueError('pos may not be the free space')
		col, row = pos
		col, row = self.cls.COL_I[col], row - 1
		i = self.cls.HEIGHT * col + row
		if col >= self.cls.COL_I['I'] and row > 2:
			i -= 1
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

class EmoteCollectorBingoBoard(BingoBoard):
	def __init__(self, *, value=None, categories=None, marks=None):
		super().__init__(value=value)
		self.categories = BingoItemWrapper(type(self), items=categories)
		self.marks = BingoItemWrapper(type(self), items=marks)
