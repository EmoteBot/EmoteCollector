#!/usr/bin/env python3
# encoding: utf-8

from datetime import datetime
import json

from flask import Flask
from flask_restful import (
	fields,
	marshal_with,
	reqparse,
	Resource,
	Api as API)
import psycopg2
import psycopg2.extras


app = Flask('emoji connoisseur API')
api = API(app, prefix='/api/v1')


def emotes(author_id=None, nsfw=False):
	"""return an iterator that gets emotes from the database.
	If author id is provided, get only emotes from them."""
	query = 'SELECT * FROM emojis '
	args = []
	if author_id is not None:
		query += 'WHERE author = %s '
		args.append(author_id)
	if nsfw:
		query += 'AND nsfw '
	query += 'ORDER BY LOWER(name)'

	with db.cursor() as cursor:
		cursor.execute(query, *args)
		yield from cursor

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
		'created': EmojiConnoisseurDateTime,
		'modified': EmojiConnoisseurDateTime,
		'description': fields.String}

	@marshal_with(fields)
	def get(self):
		return list(map(dict, emotes()))

api.add_resource(List, '/emotes')


if __name__ == '__main__':
	app.run(debug=True)
