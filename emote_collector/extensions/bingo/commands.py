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

from ...extensions.bingo.db import BoardError
from ...utils import errors
from ...utils import bingo
from ...utils.proxy import ObjectProxy

class BoardTooLewdError(BoardError):
	def __init__(self):
		super().__init__(_('An NSFW channel is required to display this board.'))

class Bingo(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.db = ObjectProxy(lambda: bot.cogs['BingoDatabase'])

	@commands.group(invoke_without_command=True)
	async def bingo(self, context):
		"""Shows you your current bingo board. All other functionality is in subcommands."""
		board = await self.db.get_board(context.author.id)
		if board.is_nsfw() and not getattr(context.channel, 'nsfw', True):
			raise BoardTooLewdError
		async with context.typing():
			f = discord.File(io.BytesIO(await bingo.render_in_subprocess(board)), f'{context.author.id}_board.png')
		await context.send(file=f)

def setup(bot):
	bot.add_cog(Bingo(bot))
