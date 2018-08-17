#!/usr/bin/env python3
# encoding: utf-8

import setuptools
import subprocess

with open('requirements.txt') as f:
	dependency_links = list(filter(lambda line: not line.startswith('#'), f))

setuptools.setup(
	name='emoji_connoisseur',
	version='0.0.1',

	packages=['emoji_connoisseur'],

	install_requires=[
		'aiocache',
		'aiocontextvars',
		'aiofiles',
		'asyncpg',
		'ben_cogs>=0.0.15',
		'discord.py',
		'jishaku>0.1.1',
		'ply',
		'prettytable',
		'sjcl',
		'wand',
	],

	dependency_links=dependency_links,
)
