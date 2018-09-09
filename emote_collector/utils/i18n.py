import builtins
import gettext
from glob import glob
import os.path

import aiocontextvars

from .. import BASE_DIR

default_locale = 'en_US'
locale_dir = 'locale'
locales = frozenset(
	map(os.path.basename,
	filter(
		os.path.isdir,
		glob(os.path.join(BASE_DIR, locale_dir, '*')))))

gettext_translations = {
	locale: gettext.translation(
		'emote_collector',
		languages=(locale,),
		localedir=os.path.join(BASE_DIR, locale_dir))
	for locale in locales}

def use_current_gettext(*args, **kwargs):
	locale = current_locale.get()
	return (
		gettext_translations.get(
			locale,
			gettext_translations[default_locale])
		.gettext(*args, **kwargs))

current_locale = aiocontextvars.ContextVar('i18n')
builtins._ = use_current_gettext

current_locale.set(default_locale)

setup = aiocontextvars.enable_inherit
