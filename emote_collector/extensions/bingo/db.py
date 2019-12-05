# Emote Collector collects emotes from other servers for use by people without Nitro
# Copyright © 2018–2019 lambda#0987
#
# Emote Collector is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Emote Collector is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Emote Collector. If not, see <https://www.gnu.org/licenses/>.

import functools
import io
import itertools
import operator

from bot_bin.sql import connection, optional_connection
from discord.ext import commands

from .errors import NoBoardError
from ... import utils
from ...utils import bingo, compose

DEFAULT_BOARD_VALUE = bingo.EmoteCollectorBingoBoard().value

class BingoDatabase(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.queries = self.bot.queries('bingo.sql')

	@optional_connection
	async def get_board(self, user_id):
		val = await connection().fetchval(self.queries.get_board_value(), user_id)
		if val is None:
			raise NoBoardError
		categories = [cat for cat, in await connection().fetch(self.queries.get_board_categories(), user_id)]
		board = bingo.EmoteCollectorBingoBoard(value=val, categories=categories)
		for mark in await connection().fetch(self.queries.get_board_marks(), user_id):
			board.marks.items[mark['pos']] = mark['nsfw'], mark['name'], mark['id'], mark['animated']
		return board

	@optional_connection
	async def new_board(self, user_id):
		async with connection().transaction(isolation='repeatable_read'):
			await connection().execute(self.queries.delete_board(), user_id)
			await connection().execute(self.queries.set_board_value(), user_id, DEFAULT_BOARD_VALUE)
			rows = await connection().fetch(self.queries.get_categories(), bingo.BingoBoard.SQUARES)
			to_insert = [
				(user_id, pos + 1 if pos >= bingo.BingoBoard.FREE_SPACE_I else pos, category_id)  # skip free space
				for pos, (category_id, category_text)
				in enumerate(rows)]
			await connection().copy_records_to_table(
				'bingo_board_categories',
				records=to_insert,
				columns=('user_id', 'pos', 'category_id'))
			return bingo.EmoteCollectorBingoBoard(categories=[category_text for __, category_text in rows])

	@optional_connection
	async def mark(self, user_id, marks):
		async with connection().transaction(isolation='repeatable_read'):
			marks = list(marks)
			params = (
				(user_id, bingo.index(point), emote.nsfw, emote.name, emote.id, emote.animated)
				for point, emote
				in marks)
			await connection().executemany(self.queries.set_board_mark(), params)
			indices = map(compose(bingo.index, operator.itemgetter(0)), marks)
			mask = functools.reduce(operator.or_, (1 << i for i in indices))
			await connection().execute(self.queries.add_board_marks_by_mask(), user_id, mask)

	@optional_connection
	async def unmark(self, user_id, points):
		indices = list(map(bingo.index, points))
		mask = functools.reduce(operator.or_, (1 << i for i in indices))
		async with connection().transaction(isolation='serializable'):
			params = list(zip(itertools.repeat(user_id), indices))
			await connection().executemany(self.queries.delete_board_mark(), params)
			await connection().execute(self.queries.delete_board_marks_by_mask(), user_id, mask)

	@optional_connection
	async def check_win(self, user_id):
		val = await connection().fetchval(self.queries.get_board_value(), user_id)
		board = bingo.EmoteCollectorBingoBoard(value=val)
		return board.has_won()

	@optional_connection
	async def delete_user_account(self, user_id):
		await connection().execute(self.queries.delete_board(), user_id)

def setup(bot):
	bot.add_cog(BingoDatabase(bot))
