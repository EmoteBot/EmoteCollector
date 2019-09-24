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

import io

from discord.ext import commands

from ...utils import bingo, errors

class BoardError(errors.ConnoisseurError):
	pass

class NoBoardError(BoardError):
	def __init__(self):
		super().__init__(_('You do not have a bingo board yet.'))

class BingoDatabase(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.queries = self.bot.jinja_env.get_template('bingo.sql')

	async def get_board(self, user_id, *, connection=None):
		row = await (connection or self.bot.pool).fetchrow(self.queries.get_board(), user_id)
		if row is None:
			raise NoBoardError
		return bingo.EmoteCollectorBingoBoard(**row)

	async def update_board(self, user_id, board, *, connection=None):
		args = bingo.marshal(board)
		row = await (connection or self.bot.pool).fetchrow(self.queries.upsert_board(), user_id, *args)
		return bingo.EmoteCollectorBingoBoard(**row)

	async def new_board(self, user_id, *, connection=None):
		board = bingo.new()
		return await self.update_board(user_id, board, connection=connection)

	async def mark(self, user_id, point, emote):
		async with self.bot.pool.acquire() as conn, conn.transaction():
			board = await self.get_board(user_id, connection=conn)
			await bingo.mark(self.bot, board, point, emote)
			return await self.update_board(user_id, board, connection=conn)

	async def check_win(self, user_id):
		board = await self.get_board(user_id)
		return board.has_won()

def setup(bot):
	bot.add_cog(BingoDatabase(bot))
