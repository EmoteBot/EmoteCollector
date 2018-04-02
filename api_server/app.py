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


def emotes(include_nsfw=False):
	"""return an iterator that gets emotes from the database.
	If author id is provided, get only emotes from them."""
	query = 'SELECT * FROM emojis '
	if not include_nsfw:
		query += 'WHERE NOT nsfw '
	query += 'ORDER BY LOWER(name)'

	return iter_from_query(query)


def emotes_by_author(author_id, include_nsfw=False):
	query = 'SELECT * FROM emojis WHERE author = %s '
	if not include_nsfw:
		query += 'AND NOT nsfw '
	query += 'ORDER BY LOWER(name)'

	return iter_from_query(query, author_id)


def get_db():
	with open('data/config.json') as config_file:
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
		'id': fields.Integer,
		'author': fields.Integer,
		'animated': fields.Boolean,
		'nsfw': fields.Boolean,
		'created': EmojiConnoisseurDateTime,
		'modified': EmojiConnoisseurDateTime,
		'description': fields.String}

	@marshal_with(fields)
	def get(self):
		parser = RequestParser()
		parser.add_argument('author', type=int, default=None)
		parser.add_argument('nsfw', type=bool)
		args = parser.parse_args()
		nsfw = 'nsfw' in args  # allow &nsfw instead of &nsfw=true
		if args.author is None:
			it = emotes(nsfw)
		else:
			it = emotes_by_author(args.author, nsfw)
		return list(map(dict, it))


api.add_resource(List, '/emotes')


if __name__ == '__main__':
	app.run(debug=True)
