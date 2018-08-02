#!/usr/bin/env python3
# encoding: utf-8

import base64
base64.Error = base64.binascii.Error
import contextlib
import secrets

import discord
from discord.ext import commands

import utils

class API:
	TOKEN_DELIMITER = b';'

	def __init__(self, bot):
		self.bot = bot
		self.bot.loop.create_task(self._init())

	async def _init(self):
		db_cog = self.bot.get_cog('Database')
		await db_cog.ready.wait()
		self._pool = db_cog._pool

	@commands.group(invoke_without_command=True)
	async def api(self, context):
		"""Commands related to the Emoji Connoisseur API.

		This command on its own will tell you a bit about the API.
		"""
		if context.invoked_subcommand is None:
			await context.send(
				'I have a RESTful API available. The docs for it are located at '
				f'{self.bot.config["api"]["docs_url"]}')

	@api.group(name='token', invoke_without_command=True)
	async def token_command(self, context):
		"""Sends you your token to use the API."""
		token = await self.token(context.author.id)
		await self.send_token(context, token)

	@token_command.command(name='regenerate')
	async def regenerate_command(self, context):
		"""Regenerates your user token. Use this if your token is compromised."""
		print('regenerate')
		token = await self.regenerate_token(context.author.id)
		await self.send_token(context, token, new=True)

	async def send_token(self, context, token, *, new=False):
		try:
			await context.author.send(
				f'Your {"new " if new else ""}API token is:\n'
				f'`{token.decode()}`\n'
				'Do **not** share it with anyone!\n'
				'\n'
				'Note: there are currently no endpoints which require this token. '
				'There may never be.')
		except discord.Forbidden:
			await context.send('Error: I could not send you your token via DMs.')
		else:
			with contextlib.suppress(discord.HTTPException):
				await context.message.add_reaction('📬')

	async def token(self, user_id):
		"""get the user's API token. If they don't already have a token, make a new one"""
		return await self.existing_token(user_id) or await self.new_token(user_id)

	async def existing_token(self, user_id):
		secret = await self._pool.fetchval("""
			SELECT secret
			FROM api_token
			WHERE id = $1
		""", user_id)
		if secret:
			return self.encode_token(user_id, secret)

	async def new_token(self, user_id):
		secret = secrets.token_bytes()
		await self._pool.execute("""
			INSERT INTO api_token (id, secret)
			VALUES ($1, $2)
		""", user_id, secret)
		return self.encode_token(user_id, secret)

	async def regenerate_token(self, user_id):
		await self._pool.execute('DELETE FROM api_token WHERE id = $1', user_id)
		return await self.new_token(user_id)

	async def validate_token(self, user_id, token):
		try:
			token_user_id, secret = self.decode_token(token)
		except:
			return False

		if token_user_id != user_id:
			return False

		return await self._pool.fetchval("""
			SELECT COALESCE((
				SELECT true
				FROM api_token
				WHERE id = $1 AND secret = $2),
			false)
		""", user_id, secret)

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
