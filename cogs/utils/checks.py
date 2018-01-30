#!/usr/bin/env python3
# encoding: utf-8

from discord.ext import commands

from utils import EXTRA_OWNERS, is_owner as is_owner_predicate


def is_owner():
	return commands.check(is_owner_predicate)
