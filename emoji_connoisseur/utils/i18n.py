import builtins
import gettext
from glob import glob
import os.path

import aiocontextvars

from .. import BASE_DIR

default_language = 'en_US'
locale_dir = 'locale'
languages = frozenset(
	map(os.path.basename,
	filter(
		os.path.isdir,
		glob(os.path.join(BASE_DIR, locale_dir, '*')))))

gettext_translations = {
	language: gettext.translation(
		'emoji_connoisseur',
		languages=(language,),
		localedir=os.path.join(BASE_DIR, locale_dir))
	for language in languages}

def use_current_gettext(*args, **kwargs):
	language = current_language.get()
	return (
		gettext_translations.get(
			language,
			gettext_translations[default_language])
		.gettext(*args, **kwargs))

current_language = aiocontextvars.ContextVar('i18n')
builtins._ = use_current_gettext

current_language.set(default_language)

setup = aiocontextvars.enable_inherit
