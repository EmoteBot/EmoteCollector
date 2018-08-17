#!/usr/bin/env sh

xgettext --files-from POTFILES.in --directory .. --output messages.pot --from-code utf-8
cat messages.pot undetected-messages.pot | sponge messages.pot

locale_dirs() {
	for locale in */; do
		printf "${locale}LC_MESSAGES"
	done
}

for locale in */; do
	msgmerge \
		--update \
		--no-fuzzy-matching \
		--backup off \
		"${locale}LC_MESSAGES/emoji_connoisseur.po" \
		messages.pot
done

if [ x$1 = "compile" ]; then
	for locale in */; do
		msgfmt \
			"${locale}LC_MESSAGES/emoji_connoisseur.po" \
			--output-file "${locale}LC_MESSAGES/emoji_connoisseur.mo"
	done
fi
