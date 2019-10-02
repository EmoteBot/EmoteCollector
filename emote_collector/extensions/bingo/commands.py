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

import discord
from discord.ext import commands

from .errors import BoardTooLewdError
from ... import utils
from ...utils import bingo, connection, optional_connection
from ...utils.converter import DatabaseOrLoggedEmote, MultiConverter
from ...utils.proxy import ObjectProxy

class Bingo(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.db = ObjectProxy(lambda: bot.cogs['BingoDatabase'])

	@commands.group(invoke_without_command=True)
	async def bingo(self, context):
		"""Shows you your current bingo board. All other functionality is in subcommands."""
		board = await self.db.get_board(context.author.id)
		await self.send_board(context, _('You win!') if board.has_won() else None, board)

	@bingo.command()
	async def new(self, context):
		"""Creates a new bingo board or replaces your current one."""
		await self.send_board(context, _('Your new bingo board:'), await self.db.new_board(context.author.id))

	@bingo.command(usage='<position> <emote>[, <position2> <emote2>...]')
	@optional_connection
	async def mark(self, context, *, args: MultiConverter[str.upper, DatabaseOrLoggedEmote]):
		"""Adds one or more marks to your board."""
		if not args:
			raise commands.BadArgument(_('You must specify at least one position and emote name.'))

		async with connection().transaction(isolation='repeatable_read'):
			await self.db.mark(context.author.id, args)
			board = await self.db.get_board(context.author.id)

		message = _('You win! Your new bingo board:') if board.has_won() else _('Your new bingo board:')
		await self.send_board(context, message, board)

	@bingo.command()
	async def unmark(self, context, *positions: str.upper):
		async with self.bot.pool.acquire() as conn:
			board = await self.db.unmark(context.author.id, positions, connection=conn)
		await self.send_board(context, _('Your new bingo board:'), board)

	async def send_board(self, context, message, board):
		if board.is_nsfw() and not getattr(context.channel, 'nsfw', True):
			raise BoardTooLewdError
		async with context.typing():
			f = discord.File(
				io.BytesIO(await bingo.render_in_subprocess(self.bot, board)),
				f'{context.author.id}_board.png')
		await context.send(message, file=f)

def setup(bot):
	bot.add_cog(Bingo(bot))
