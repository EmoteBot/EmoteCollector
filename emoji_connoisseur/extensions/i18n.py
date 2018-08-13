#!/usr/bin/env python3
# encoding: utf-8

import gettext

import aiocontextvars

var = aiocontextvars.ContextVar('i18n')

default_language = 'en_US'
languages = ('en_US',)
gettext_translations = {
	lang: gettext.translation('emoji_connoisseur', languages=(lang,), localedir='locale')
	for lang in languages}

def use_current_gettext(*args, **kwargs):
	language = var.get()
	return gettext_translations.get(language, default_language).gettext(*args, **kwargs)

def i18n_setup(loop):
	import builtins
	builtins._ = use_current_gettext

	aiocontextvars.enable_inherit(loop)

	var.set(default_language)

class Internationalization:
	def __init__(self, bot):
		self.bot = bot
		i18n_setup(self.bot.loop)
		self.db = self.bot.get_cog('Database')

	async def set_language(self, message):
		language = await self.db.language(message.guild.id, message.channel.id, message.author.id)
		var.set(language)

def setup(bot):
	bot.add_cog(Internationalization(bot))
