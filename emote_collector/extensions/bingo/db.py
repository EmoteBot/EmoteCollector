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

from discord.ext import commands

from .errors import NoBoardError
from ... import utils
from ...utils import bingo, compose, connection, optional_connection

class BingoDatabase(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.queries = self.bot.jinja_env.get_template('bingo.sql')

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
			board = bingo.new()
			await connection().execute(self.queries.delete_board(), user_id)
			await connection().execute(self.queries.set_board_value(), user_id, board.value)
			categories = ((user_id, i, cat) for i, cat in enumerate(board.categories.items) if cat is not None)
			await connection().executemany(self.queries.set_board_category(), categories)
			return board

	@optional_connection
	async def mark(self, user_id, marks):
		async with connection().transaction(isolation='repeatable_read'):
			marks = list(marks)
			params = (
				(user_id, bingo.board.index(point), emote.nsfw, emote.name, emote.id, emote.animated)
				for point, emote
				in marks)
			await connection().executemany(self.queries.set_board_mark(), params)
			indices = map(compose(bingo.board.index, operator.itemgetter(0)), marks)
			mask = functools.reduce(operator.or_, (1 << i for i in indices))
			await connection().execute(self.queries.add_board_marks_by_mask(), user_id, mask)

	@optional_connection
	async def unmark(self, user_id, points):
		indices = list(map(bingo.board.index, points))
		mask = functools.reduce(operator.or_, (1 << i for i in indices))
		async with connection().transaction(isolation='serializable'):
			params = list(zip(itertools.repeat(user_id), indices))
			await connection().executemany(self.queries.delete_board_mark(), params)
			await connection().execute(self.queries.delete_board_marks_by_mask(), user_id, mask)

	@optional_connection
	async def check_win(self, user_id, connection=None):
		val = await connection().fetchval(self.queries.get_board_value(), user_id)
		board = bingo.EmoteCollectorBingoBoard(value=val)
		return board.has_won()

def setup(bot):
	bot.add_cog(BingoDatabase(bot))
