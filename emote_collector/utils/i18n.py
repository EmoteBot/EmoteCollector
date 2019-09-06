# Emote Collector collects emotes from other servers for use by people without Nitro
# Copyright © 2018–2019 lambda#0987
#
# Emote Collector is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Emote Collector is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Emote Collector. If not, see <https://www.gnu.org/licenses/>.

import builtins
import gettext
from glob import glob
import os.path

import aiocontextvars

from .. import BASE_DIR

default_locale = 'en_US'
locale_dir = 'locale'
locales = frozenset(p.name for p in (BASE_DIR / locale_dir).iterdir() if p.is_dir())

gettext_translations = {
	locale: gettext.translation(
		'emote_collector',
		languages=(locale,),
		localedir=os.path.join(BASE_DIR, locale_dir))
	for locale in locales}

# source code is already in en_US.
# we don't use default_locale as the key here
# because the default locale for this installation may not be en_US
gettext_translations['en_US'] = gettext.NullTranslations()
locales = locales | {'en_US'}

def use_current_gettext(*args, **kwargs):
	if not gettext_translations:
		return gettext.gettext(*args, **kwargs)

	locale = current_locale.get()
	return (
		gettext_translations.get(
			locale,
			gettext_translations[default_locale])
		.gettext(*args, **kwargs))

current_locale = aiocontextvars.ContextVar('i18n')
builtins._ = use_current_gettext

def set_default_locale(): current_locale.set(default_locale)
set_default_locale()
