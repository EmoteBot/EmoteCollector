#!/usr/bin/env python3
# encoding: utf-8

from datetime import datetime

from flask import Flask
from flask_restful import (
	fields,
	marshal_with,
	Resource,
	Api as API)
from flask_restful.reqparse import RequestParser

import db


app = Flask('emoji connoisseur API')
api = API(app, prefix='/api/v0')


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
		'created': EmojiConnoisseurDateTime,
		'modified': EmojiConnoisseurDateTime,
		'description': fields.String}

	@marshal_with(fields)
	def get(self):
		parser = RequestParser()
		parser.add_argument('author', type=int, default=None)
		args = parser.parse_args()
		return list(map(dict, db.emotes(args.author)))


api.add_resource(List, '/emotes')


if __name__ == '__main__':
	app.run(debug=True)
