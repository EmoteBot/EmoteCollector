#!/usr/bin/env python3
# encoding: utf-8

import json

import psycopg2
import psycopg2.extras


def iter_from_query(query, *args):
	"""return an iterator from a query that retrieves multiple records"""
	with db.cursor() as cursor:
		cursor.execute(query, args)
		yield from cursor


def format_sql_conditions(conditions):
	"""format a sequence of SQL predicates as a single WHERE clause"""
	if not conditions:
		return ''
	return 'WHERE ' + ' AND '.join(conditions) + ' '


def emotes(author_id=None, include_nsfw=False):
	"""return an iterator that gets emotes from the database.
	If author id is provided, get only emotes from them.
	If include_nsfw, list all emotes."""
	query = 'SELECT * FROM emojis '
	conditions = []
	args = []
	if author_id is not None:
		conditions.append('author = %s')
		args.append(author_id)
	if not include_nsfw:
		conditions.append('NOT nsfw')

	query += format_sql_conditions(conditions)
	query += 'ORDER BY LOWER(name)'
	print(query)
	return iter_from_query(query, *args)


def get_db():
	with open('../data/config.json') as config_file:
		credentials = json.load(config_file)['database']

	# pylint: disable=invalid-name
	db = psycopg2.connect(**credentials, cursor_factory=psycopg2.extras.DictCursor)
	db.autocommit = True
	return db


# hides the temporary variables like credentials and config_file
db = get_db()  # pylint: disable=invalid-name
