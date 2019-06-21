#!/usr/bin/env python3
# encoding: utf-8

import base64
import contextlib
import secrets

import discord
from discord.ext import commands

from .. import utils

class API(commands.Cog):
	TOKEN_DELIMITER = b';'

	def __init__(self, bot):
		self.bot = bot

	@staticmethod
	def any_parent_command_is(command, parent_command):
		while command is not None:
			if command is parent_command:
				return True
			command = command.parent
		return False

	async def cog_check(self, context):
		# we're doing this as a local check because
		# A) if invoke_without_command=True, checks don't propagate to subcommands
		# B) even if invoke_without_command=False, checks still don't propagate to sub-sub-commands
		# AFAIK
		if self.any_parent_command_is(context.command, self.token_command):
			# bots may not have API tokens
			return not context.author.bot
		return True

	@commands.group(invoke_without_command=True)
	async def api(self, context):
		"""Commands related to the Emote Collector API.

		This command on its own will tell you a bit about the API.
		"""
		if context.invoked_subcommand is None:
			await context.send(_(
				'I have a RESTful API available. The docs for it are located at '
				'{docs_url}.').format(docs_url=self.bot.config['api']['docs_url']))

	@api.group(name='token', aliases=('toke1', 'toke', 'tok'), invoke_without_command=True)
	async def token_command(self, context):
		"""Sends you your token to use the API."""
		token = await self.token(context.author.id)
		await self.send_token(context, token)

	@token_command.command(name='regenerate', aliases=('regen',))
	async def regenerate_command(self, context):
		"""Regenerates your user token. Use this if your token is compromised."""
		token = await self.regenerate_token(context.author.id)
		await self.send_token(context, token, new=True)

	async def send_token(self, context, token, *, new=False):
		if new:
			first_line = _('Your new API token is:\n')
		else:
			first_line = _('Your API token is:\n')

		message = (
			first_line
			+ f'`{token.decode()}`\n'
			+ _('Do **not** share it with anyone!'))

		try:
			await context.author.send(message)
		except discord.Forbidden:
			await context.send(_('Error: I could not send you your token via DMs.'))
		else:
			with contextlib.suppress(discord.HTTPException):
				await context.message.add_reaction('📬')

	async def token(self, user_id):
		"""get the user's API token. If they don't already have a token, make a new one"""
		return await self.existing_token(user_id) or await self.new_token(user_id)

	async def delete_user_account(self, user_id):
		await self.bot.pool.execute('DELETE FROM api_tokens WHERE id = $1', user_id)

	async def existing_token(self, user_id):
		secret = await self.bot.pool.fetchval("""
			SELECT secret
			FROM api_tokens
			WHERE id = $1
		""", user_id)
		if secret:
			return self.encode_token(user_id, secret)

	async def new_token(self, user_id):
		secret = secrets.token_bytes()
		await self.bot.pool.execute("""
			INSERT INTO api_tokens (id, secret)
			VALUES ($1, $2)
		""", user_id, secret)
		return self.encode_token(user_id, secret)

	async def regenerate_token(self, user_id):
		await self.bot.pool.execute('DELETE FROM api_tokens WHERE id = $1', user_id)
		return await self.new_token(user_id)

	async def validate_token(self, token, user_id=None):
		try:
			token_user_id, secret = self.decode_token(token)
		except:
			secrets.compare_digest(token, token)
			return False

		if user_id is None:
			# allow auth with just a secret
			user_id = token_user_id

		db_secret = await self.bot.pool.fetchval("""
			SELECT secret
			FROM api_tokens
			WHERE id = $1
		""", user_id)
		if db_secret is None:
			secrets.compare_digest(token, token)
			return False

		db_token = self.encode_token(user_id, db_secret)
		return secrets.compare_digest(token, db_token) and user_id

	def generate_token(self, user_id):
		secret = base64.b64encode(secrets.token_bytes())
		return self.encode_token(user_id, secret)

	def encode_token(self, user_id, secret: bytes):
		return base64.b64encode(utils.int_to_bytes(user_id)) + self.TOKEN_DELIMITER + base64.b64encode(secret)

	def decode_token(self, token):
		user_id, secret = map(base64.b64decode, token.split(self.TOKEN_DELIMITER))
		user_id = utils.bytes_to_int(user_id)

		return user_id, secret

def setup(bot):
	if bot.config.get('api'):
		bot.add_cog(API(bot))
