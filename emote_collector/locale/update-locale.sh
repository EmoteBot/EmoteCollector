#!/usr/bin/env sh

xgettext --files-from POTFILES.in --directory ../../ --output messages.pot --from-code utf-8

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
		"${locale}LC_MESSAGES/emote_collector.po" \
		messages.pot
done

if [ x$1 = "xcompile" ]; then
	for locale in */; do
		msgfmt \
			"${locale}LC_MESSAGES/emote_collector.po" \
			--output-file "${locale}LC_MESSAGES/emote_collector.mo"
	done
fi
