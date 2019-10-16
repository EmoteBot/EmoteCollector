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

import contextlib

from discord.ext import commands

from .. import BASE_DIR
from .. import utils

MEMES_FILE = BASE_DIR / 'data' / 'memes.py'

class Meme(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.memes = utils.load_json_compat(MEMES_FILE)

	@commands.command(hidden=True)
	async def meme(self, context, *, name):
		with contextlib.suppress(KeyError):
			await context.send(self.memes[name])

def setup(bot):
	if MEMES_FILE.exists():
		bot.add_cog(Meme(bot))
