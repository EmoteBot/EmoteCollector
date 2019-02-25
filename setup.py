#!/usr/bin/env python3
# encoding: utf-8

import os.path

import pkg_resources
import setuptools

actual_pip_version = pkg_resources.get_distribution('pip').parsed_version
# this class recently moved packages
Version = type(actual_pip_version)
required_pip_version = Version('18.1')

if not actual_pip_version >= required_pip_version:
	raise RuntimeError(f'pip >= {required_pip_version} required')

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
		'aiocontextvars==0.1.2',
		'asyncpg',
		'ben_cogs>=0.8.0',
		# apparently the following two requirements can't be combined
		# per the grammar (https://www.python.org/dev/peps/pep-0508/#grammar)
		'discord.py @ git+https://github.com/Rapptz/discord.py@rewrite',
		'discord.py>=1.0.0a1691',
		'jishaku>=1.6.1,<2.0.0',
		'ply',
		'prettytable',
		'wand',
	],
)
