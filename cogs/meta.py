#!/usr/bin/env python3
# encoding: utf-8

import discord
from discord.ext import commands


class Meta:
	def __init__(self, bot):
		self.bot = bot

	@commands.command()
	async def invite(self, context):
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
		await context.send('<%s>' % discord.utils.oauth_url(self.bot.client_id, permissions))


def setup(bot):
	bot.add_cog(Meta(bot))
