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

"""
various utilities related to custom emotes and regular emojis
"""

import os.path
import json

import discord

from .. import BASE_DIR

with open(BASE_DIR / 'data' / 'discord-emoji-shortcodes.json') as f:
	emoji_shortcodes = frozenset(json.load(f))
del f

def url(id, *, animated: bool = False):
	"""Convert an emote ID to the image URL for that emote."""
	return str(discord.PartialEmoji(animated=animated, name='', id=id).url)
