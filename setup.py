#!/usr/bin/env python3
# encoding: utf-8

import os.path

import setuptools
import subprocess

with open('requirements.txt') as f:
	dependency_links = list(filter(lambda line: not line.startswith('#'), f))

setuptools.setup(
	name='emote_collector',
	version='0.0.1',

	packages=[
		'emote_collector',
		'emote_collector.utils',
		'emote_collector.extensions',
	],


	# include stuff in MANIFEST.in (i think)
	include_package_data=True,

	install_requires=[
		'aiocontextvars==0.1.2',
		'asyncpg',
		'ben_cogs>=0.0.15',
		'discord.py',
		'jishaku>0.1.1',
		'ply',
		'prettytable',
		'wand',
	],

	dependency_links=dependency_links,
)
