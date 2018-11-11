import asyncio
import discord

class BetterTyping(discord.context_managers.Typing):
	async def do_typing(self):
		await asyncio.sleep(1)
		await super().do_typing()

	async def __aenter__(self):
		return self.__enter__()

discord.abc.Messageable.typing = lambda self: BetterTyping(self)
