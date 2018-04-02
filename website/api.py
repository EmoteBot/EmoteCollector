#!/usr/bin/env python3
# encoding: utf-8

from datetime import datetime
import json

from flask import Flask
from flask_restful import (
	fields,
	marshal_with,
	Resource,
	Api as API)
from flask_restful.reqparse import RequestParser
import psycopg2
import psycopg2.extras


app = Flask('emoji connoisseur API')
api = API(app, prefix='/api/v0')


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

	db = psycopg2.connect(**credentials, cursor_factory=psycopg2.extras.DictCursor)
	db.autocommit = True
	return db


# hides the temporary variables like credentials and config_file
db = get_db()


class EmojiConnoisseurDateTime(fields.Raw):
	EPOCH = 1518652800  # February 15, 2018, the date of the first emote

	@classmethod
	def format(cls, time: datetime):
		# time.timestamp() is a float, but we don't need that much precision
		return int(time.timestamp()) - cls.EPOCH


class List(Resource):
	fields = {
		'name': fields.String,
		'id': fields.String,  # JSON cannot handle large nums
		'author': fields.String,  # same here
		'animated': fields.Boolean,
		'nsfw': fields.Boolean,
		'created': EmojiConnoisseurDateTime,
		'modified': EmojiConnoisseurDateTime,
		'description': fields.String}

	@marshal_with(fields)
	def get(self):
		parser = RequestParser()
		parser.add_argument('author', type=int, default=None)
		parser.add_argument('nsfw', store_missing=False)
		args = parser.parse_args()
		include_nsfw = 'nsfw' in args
		return list(map(dict, emotes(args.author, include_nsfw)))


api.add_resource(List, '/emotes')


if __name__ == '__main__':
	app.run(debug=True)
