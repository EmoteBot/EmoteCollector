#!/usr/bin/env sh

xgettext \
	--files-from POTFILES.in \
	--from-code utf-8 \
	--add-comments \
	--directory ../../ \
	--output messages.pot

for locale in */; do
	file="$locale/LC_MESSAGES/emote_collector"

	msgmerge \
		--update \
		--no-fuzzy-matching \
		--backup off \
		"$file.po" \
		messages.pot

	msgfmt "$file.po" --output-file "$file.mo"; done
