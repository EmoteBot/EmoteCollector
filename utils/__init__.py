#!/usr/bin/env python3
# encoding: utf-8

"""
Various utils that for whatever reason cannot or should not go in a cog
Most of the time, this is due to them being needed outside of cog scope, or accessible
without accessing Bot.

Note: try to put stuff in the Utils cog. Any code that goes in here requires a restart of the entire
bot in order to update. Any stuff that goes in Utils can be hot reloaded without downtime.
"""

import re
import urllib.parse

import discord
from discord.ext import commands
import discord.utils

# this import comes first, as later imports depend on it
from .misc import *

from . import checks
from . import context
from . import converter
from . import errors
from . import paginator
