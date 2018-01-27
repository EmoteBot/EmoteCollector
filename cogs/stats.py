#!/usr/bin/env python3
# encoding: utf-8

from functools import wraps


import json
import aiohttp


class StatsAPI:
	# credit to "ﾠﾠﾠﾠ#7887" on the Discord Bots List guild
	# for much of this
	def __init__(self, bot):
		self.bot = bot
		self.session = aiohttp.ClientSession(loop=bot.loop)
		self.config = self.bot.config['tokens']['stats']

	def __unload(self):
		self.bot.loop.create_task(self.session.close())

	async def send(self, url, headers={}, data={}):
		"""send the statistics to the API gateway."""
		async with self.session.post(
			url,
			data=data,
			headers=headers)\
		as resp:
			print('[STATS]', self.config_section, end=' ')
			if resp.status != 200:
				print('failed with status code', resp.status)
			else:
				print('response:', await resp.text())

	@property
	def api_key(self):
		return self.config[self.config_section]

	@property
	def guild_count(self):
		return len(self.bot.guilds)

	async def on_ready(self):
		await self.send()

	async def on_guild_join(self, server):
		await self.send()

	async def on_guild_remove(self, server):
		await self.send()


class DiscordPwStats(StatsAPI):
	config_section = 'bots.discord.pw'

	async def send(self):
		await super().send(
			'https://bots.discord.pw/api/bots/{}/stats'.format(self.bot.user.id),
			data=json.dumps({'server_count': self.guild_count}),
			headers={
				'Authorization': self.api_key,
				'Content-Type': 'application/json'})


class DiscordBotList(StatsAPI):
	config_section = 'discordbots.org'

	# make sure that __name__ and stuff are updated
	send = wraps(DiscordPwStats.send)


class Discordlist(StatsAPI):
	config_section = 'bots.discordlist.net'

	async def send(self):
		await super().send(
			'https://bots.discordlist.net/api',
			data=json.dumps({
				'token': self.api_key,
				'server_count': self.guild_count}),
			headers={'Content-Type': 'application/json'})


def setup(bot):
	for Cog in (DiscordPwStats, DiscordBotList, Discordlist):
		stats_config = bot.config['tokens']['stats']
		if stats_config.get(Cog.config_section):
			bot.add_cog(Cog(bot))
		else:
			print(
				Cog.config_section,
				"was not loaded! Please make sure it's configured properly.")
