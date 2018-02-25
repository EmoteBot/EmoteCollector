#!/usr/bin/env python3
# encoding: utf-8

import asyncio
import json
import logging
from pathlib import Path

import asyncpg


logger = logging.getLogger('db')
logger.setLevel(logging.WARNING)


DATA_DIR = Path('data')
with open(str(DATA_DIR / 'config.json')) as config_file:
	CONFIG = json.load(config_file)
del config_file


async def _get_db():
	credentials = CONFIG['database']

	try:
		db = await asyncpg.create_pool(**credentials)
	except ConnectionRefusedError as exception:
		logger.error('%s: %s', type(exception).__name__, exception)
		sys.exit(1)

	await db.execute('SET TIME ZONE UTC')  # make sure timestamps are displayed correctly
	await db.execute('CREATE SCHEMA IF NOT EXISTS connoisseur')
	await db.execute("""
		CREATE TABLE IF NOT EXISTS emojis(
			name VARCHAR(32) NOT NULL,
			id BIGINT NOT NULL UNIQUE,
			author BIGINT NOT NULL,
			animated BOOLEAN DEFAULT FALSE,
			description VARCHAR(280),
			created TIMESTAMP WITH TIME ZONE DEFAULT (now() at time zone 'UTC'),
			modified TIMESTAMP WITH TIME ZONE)""")
	await db.execute("""
		-- https://stackoverflow.com/a/26284695/1378440
		CREATE OR REPLACE FUNCTION update_modified_column()
		RETURNS TRIGGER AS $$
		BEGIN
			IF row(NEW.*) IS DISTINCT FROM row(OLD.*) THEN
				NEW.modified = now() at time zone 'UTC';
				RETURN NEW;
			ELSE
				RETURN OLD;
			END IF;
		END;
		$$ language 'plpgsql';""")
	await db.execute('DROP TRIGGER IF EXISTS update_emoji_modtime ON emojis')
	await db.execute("""
		CREATE TRIGGER update_emoji_modtime
		BEFORE UPDATE ON emojis
		FOR EACH ROW EXECUTE PROCEDURE update_modified_column();""")
	await db.execute('CREATE TABLE IF NOT EXISTS connoisseur.blacklists(id bigint NOT NULL UNIQUE)')
	return db


DB = asyncio.get_event_loop().run_until_complete(_get_db())
