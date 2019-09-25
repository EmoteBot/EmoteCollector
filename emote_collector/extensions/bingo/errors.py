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

from ...utils.errors import ConnoisseurError

class BingoError(ConnoisseurError):
	pass

class NoBoardError(BingoError):
	def __init__(self):
		super().__init__(_('You do not have a bingo board yet.'))

class BoardTooLewdError(BingoError):
	def __init__(self):
		super().__init__(_('An NSFW channel is required to display this board.'))
