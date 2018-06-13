#!/usr/bin/env python3.6
# encoding: utf-8

import discord
from discord.ext import commands


class Meta:
	def __init__(self, bot):
		self.bot = bot

	@commands.command()
	async def support(self, context):
		"""Directs you the support server."""
		try:
			await context.author.send('https://discord.gg/' + self.bot.config['support_server_invite_code'])
			await context.try_add_reaction('\N{open mailbox with raised flag}')
		except discord.HTTPException:
			await context.try_add_reaction('\N{cross mark}')
			await context.send('Unable to send invite in DMs. Please allow DMs from server members.')

	@commands.command()
	async def invite(self, context):
		"""Gives you a link to add me to your server."""
		# these are the same as the attributes of discord.Permissions
		permission_names = (
			'read_messages',
			'send_messages',
			'read_message_history',
			'external_emojis',
			'add_reactions',
			'manage_messages',
			'embed_links')
		permissions = discord.Permissions()
		permissions.update(**dict.fromkeys(permission_names, True))
		await context.send('<%s>' % discord.utils.oauth_url(self.bot.config['client_id'], permissions))


def setup(bot):
	bot.add_cog(Meta(bot))
