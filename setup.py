#!/usr/bin/env python3
# encoding: utf-8

import setuptools

setuptools.setup(
	name='emote_collector',
	version='0.0.1',

	packages=[
		'emote_collector',
		'emote_collector.utils',
		'emote_collector.extensions',
	],

	include_package_data=True,

	install_requires=[
		'aiocontextvars>=0.2.2',
		'asyncpg',
		'bot_bin[sql]>=1.0.0,<2.0.0',
		'discord.py>=1.1.1,<2.0.0',
		'jishaku>=1.6.1,<2.0.0',
		'ply',
		'psutil',
		'pygit2',
		'querypp>=1.0.1,<2.0.0',
		'wand',
	],
)
