#!/usr/bin/env python3
# encoding: utf-8

import shlex
import os
import weakref

import psutil

import discord
from discord.ext import commands

from ..utils import argparse
from ..utils.i18n import _
from ..utils.paginator import HelpPaginator

class Meta:
	def __init__(self, bot):
		self.bot = bot
		# setting a Command as an attribute of a cog causes it to be added to the bot
		# prevent this by wrapping it in a tuple
		self.old_help = (self.bot.remove_command('help'),)
		self.paginators = weakref.WeakSet()
		self.process = psutil.Process()

	def __unload(self):
		for paginator in self.paginators:
			self.bot.loop.create_task(paginator.stop(delete=False))

	@commands.command()
	async def help(self, context, *, args: str=None):
		if args is None:
			paginator = await HelpPaginator.from_bot(context)
			self.paginators.add(paginator)
			return await paginator.begin()

		parser = argparse.ArgumentParser(
			prog=context.command.name,
			add_help=True,
			description='Shows help about a command, category, or the bot.')

		parser.add_argument('--embed', dest='embed', action='store_true', help='display output with an embed')
		parser.add_argument('--no-embed', dest='embed', action='store_false', help='display output without an embed')
		parser.set_defaults(embed=True)
		parser.add_argument('command or category', nargs='*')

		try:
			parsed_args = parser.parse_args(shlex.split(args))
		except argparse.ArgumentParserError as e:
			return await context.send(e)

		command = getattr(parsed_args, 'command or category') or ()

		if not parsed_args.embed:
			return await context.invoke(self.old_help[0], *command)

		# derived from R.Danny's help command
		# https://github.com/Rapptz/RoboDanny/blob/8919ec0a455f957848ef77b479fe3494e76f0aa7/cogs/meta.py
		# MIT Licensed, Copyright © 2015 Rapptz

		# it came from argparser so it's still a bunch of args
		command = ' '.join(command)
		entity = self.bot.get_cog(command) or self.bot.get_command(command)

		if entity is self.help:
			return await context.send(f'```{parser.format_help()}```')
		if entity is None:
			clean = command.replace('@', '@\N{zero width non-joiner}')
			return await context.send(f'Command or category "{clean}" not found.')
		elif isinstance(entity, commands.Command):
			paginator = await HelpPaginator.from_command(context, entity)
		else:
			paginator = await HelpPaginator.from_cog(context, entity)

		self.paginators.add(paginator)
		await paginator.begin()

	@commands.command()
	async def about(self, context):
		"""Tells you information about the bot itself."""
		# this command is based off of code provided by Rapptz under the MIT license
		# https://github.com/Rapptz/RoboDanny/blob/f6638d520ea0f559cb2ae28b862c733e1f165970/cogs/stats.py
		# Copyright © 2015 Rapptz

		embed = discord.Embed(description=self.bot.config['description'])

		embed.add_field(name='Latest changes', value=self._latest_changes(), inline=False)

		embed.title = 'Official Bot Support Invite'
		embed.url = 'https://discord.gg/' + self.bot.config['support_server_invite_code']

		owner = self.bot.get_user(self.bot.config.get('primary_owner', self.bot.owner_id))
		embed.set_author(name=str(owner), icon_url=owner.avatar_url)

		embed.add_field(name='Servers', value=await self.bot.get_cog('Stats').guild_count())

		debug_cog = self.bot.get_cog('Debug')
		cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
		embed.add_field(name='Process', value=f'{debug_cog.memory_usage()}\n{cpu_usage:.2f}% CPU')

		embed.add_field(name='Uptime', value=self.bot.get_cog('Misc').uptime(brief=True))
		embed.set_footer(text='Made with discord.py', icon_url='http://i.imgur.com/5BFecvA.png')

		await context.send(embed=embed)

	def _latest_changes(self):
		cmd = fr'git show -s HEAD~3..HEAD --format="[{{}}]({self.bot.config["repo"]}/commit/%H) %s (%cr)"'
		if os.name == 'posix':
			cmd = cmd.format(r'\`%h\`')
		else:
			cmd = cmd.format(r'`%h`')

		try:
			return os.popen(cmd).read().strip()
		except OSError:
			return 'Could not fetch due to memory error. Sorry.'

	@commands.command()
	async def support(self, context):
		"""Directs you to the support server."""
		try:
			await context.author.send('https://discord.gg/' + self.bot.config['support_server_invite_code'])
			await context.try_add_reaction('\N{open mailbox with raised flag}')
		except discord.HTTPException:
			await context.try_add_reaction('\N{cross mark}')
			await context.send('Unable to send invite in DMs. Please allow DMs from server members.')

	@commands.command(aliases=['inv'])
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
