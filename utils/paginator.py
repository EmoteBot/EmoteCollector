import asyncio
import typing

import discord
from discord.ext.commands import Context


# Copyright © 2016-2017 Pandentia and contributors
# https://github.com/Thessia/Liara/blob/75fa11948b8b2ea27842d8815a32e51ef280a999/cogs/utils/paginator.py


class Paginator:
	def __init__(self, ctx: Context, pages: typing.Iterable, *, timeout=300, delete_message=False, predicate=None,
				 delete_message_on_timeout=False):
		if predicate is None:
			def predicate(_, user):
				return user == ctx.message.author

		self.pages = list(pages)
		self.predicate = predicate
		self.timeout = timeout
		self.target = ctx.channel
		self.delete_msg = delete_message
		self.delete_msg_timeout = delete_message_on_timeout

		self._stopped = None  # we use this later
		self._embed = None
		self._message = None
		self._client = ctx.bot

		self.footer = 'Page {} of {}'
		self.navigation = {
			'\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}': self.first_page,
			'\N{BLACK LEFT-POINTING TRIANGLE}': self.previous_page,
			'\N{BLACK RIGHT-POINTING TRIANGLE}': self.next_page,
			'\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}': self.last_page,
			'\N{BLACK SQUARE FOR STOP}': self.stop
		}

		self._page = None

	async def begin(self):
		"""Starts pagination"""
		self._stopped = False
		self._embed = discord.Embed()
		await self.first_page()
		for button in self.navigation:
			await self._message.add_reaction(button)
		while not self._stopped:
			try:
				reaction, user = await self._client.wait_for('reaction_add', check=self.predicate, timeout=self.timeout)
			except asyncio.TimeoutError:
				await self.stop(delete=self.delete_msg_timeout)
				continue

			reaction = reaction.emoji

			if reaction not in self.navigation:
				continue  # not worth our time

			await self.navigation[reaction]()

			await asyncio.sleep(0.2)
			try:
				await self._message.remove_reaction(reaction, user)
			except discord.HTTPException:
				pass  # oh well, we tried

	async def stop(self, *, delete=None):
		"""Aborts pagination."""
		if delete is None:
			delete = self.delete_msg

		if delete:
			await self._message.delete()
		else:
			await self._clear_reactions()
		self._stopped = True

	async def _clear_reactions(self):
		try:
			await self._message.clear_reactions()
		except discord.Forbidden:
			for button in self.navigation:
				await self._message.remove_reaction(button, self._message.author)

	async def format_page(self):
		self._embed.description = self.pages[self._page]
		self._embed.set_footer(text=self.footer.format(self._page + 1, len(self.pages)))
		if self._message:
			await self._message.edit(embed=self._embed)
		else:
			self._message = await self.target.send(embed=self._embed)

	async def first_page(self):
		self._page = 0
		await self.format_page()

	async def next_page(self):
		self._page += 1
		if self._page == len(self.pages):  # avoid the inevitable IndexError
			self._page = 0
		await self.format_page()

	async def previous_page(self):
		self._page -= 1
		if self._page < 0:	# ditto
			self._page = len(self.pages) - 1
		await self.format_page()

	async def last_page(self):
		self._page = len(self.pages) - 1
		await self.format_page()


class ListPaginator(Paginator):
	def __init__(self, ctx, _list: list, per_page=10, **kwargs):
		pages = []
		page = ''
		c = 0
		l = len(_list)
		for i in _list:
			if c > l:
				break
			if c % per_page == 0 and page:
				pages.append(page.strip())
				page = ''
			page += '{}. {}\n'.format(c+1, i)

			c += 1
		pages.append(page.strip())
		# shut up, IDEA
		# noinspection PyArgumentList
		super().__init__(ctx, pages, **kwargs)
		self.footer += ' ({} entries)'.format(l)
