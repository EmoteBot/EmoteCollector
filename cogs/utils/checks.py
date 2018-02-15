#!/usr/bin/env python3
# encoding: utf-8

from discord.ext import commands

import utils


def is_owner():
	return commands.check(utils.is_owner)
