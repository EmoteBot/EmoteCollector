#!/usr/bin/env python3
# encoding: utf-8

import asyncio
from pathlib import Path
import json


import aiosqlite
from sqlite_object import SqliteDict as _SQLiteDict
from sqlite_object import SqliteList as _SQLiteList


def _get_config():
	with open(DATA_DIR/'config.json') as config_file:
		config = json.load(config_file)
	return config


async def _get_dbs(db_name):
	for db_name in ('emojis', 'blacklists'):
		
	return await aiosqlite.connect(str(DATA_DIR/db_name))

DATA_DIR = Path('data')
CONFIG = _get_config()
EMOJIS = 