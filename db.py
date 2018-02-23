#!/usr/bin/env python3
# encoding: utf-8

import asyncio
from pathlib import Path
import json

import asyncpg


def _get_config():
	with open(str(DATA_DIR / 'config.json')) as config_file:
		config = json.load(config_file)
	return config


async def _get_db():
	credentials = CONFIG['database']
	db = await asyncpg.create_pool(**credentials)
	await db.execute('CREATE SCHEMA IF NOT EXISTS connoisseur')
	await db.execute("""
		CREATE TABLE IF NOT EXISTS emojis(
			name VARCHAR(32) NOT NULL,
			id BIGINT NOT NULL UNIQUE,
			author BIGINT NOT NULL,
			animated BOOLEAN DEFAULT FALSE,
			description VARCHAR(280),
			created timestamp without time zone default (now() at time zone 'utc'),
			modified timestamp without time zone)""")
	await db.execute("""
		-- https://stackoverflow.com/a/26284695/1378440
		CREATE OR REPLACE FUNCTION update_modified_column()
		RETURNS TRIGGER AS $$
		BEGIN
			IF row(NEW.*) IS DISTINCT FROM row(OLD.*) THEN
				NEW.modified = now() at time zone 'utc';
				RETURN NEW;
			ELSE
				RETURN OLD;
			END IF;
		END;
		$$ language 'plpgsql';""")
	await db.execute("""
		DROP TRIGGER IF EXISTS update_emoji_modtime ON emojis;

		CREATE TRIGGER update_emoji_modtime
		BEFORE UPDATE ON emojis
		FOR EACH ROW EXECUTE PROCEDURE update_modified_column();""")
	await db.execute('CREATE TABLE IF NOT EXISTS connoisseur.blacklists(id bigint NOT NULL UNIQUE)')
	return db


DATA_DIR = Path('data')
CONFIG = _get_config()
DB = asyncio.get_event_loop().run_until_complete(_get_db())
