#!/usr/bin/env python3
# encoding: utf-8

from flask import Flask, Response

import db

app = Flask('emoji-connoisseur')
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

@app.route('/list')
@app.route('/list/<int:author>')
def list(author=None):
	return Response(stream_template('list.html', emotes=db.emotes(author), author=author))

# http://flask.pocoo.org/docs/1.0/patterns/streaming/#streaming-from-templates
def stream_template(template_name, **context):
	app.update_template_context(context)
	template = app.jinja_env.get_template(template_name)
	template_stream = template.stream(context)
	template_stream.enable_buffering(5)
	return template_stream

def emote_url(emote_id, animated: bool = False):
	"""Convert an emote ID to the image URL for that emote."""
	return f'https://cdn.discordapp.com/emojis/{emote_id}{".gif" if animated else ".png"}?v=1'

app.jinja_env.globals['emote_url'] = emote_url
