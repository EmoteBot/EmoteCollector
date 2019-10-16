-- Emote Collector collects emotes from other servers for use by people without Nitro
-- Copyright © 2019 lambda#0987
--
-- Emote Collector is free software: you can redistribute it and/or modify
-- it under the terms of the GNU Affero General Public License as
-- published by the Free Software Foundation, either version 3 of the
-- License, or (at your option) any later version.
--
-- Emote Collector is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
-- GNU Affero General Public License for more details.
--
-- You should have received a copy of the GNU Affero General Public License
-- along with Emote Collector. If not, see <https://www.gnu.org/licenses/>.

-- :macro locale()
-- params: user_id, channel_id, guild_id (may be null)
SELECT COALESCE(
	(
		SELECT locale
		FROM locales
		WHERE "user" = $1),
	(
		SELECT locale
		FROM locales
		WHERE channel = $2),
	(
		SELECT locale
		FROM locales
		WHERE
			guild = $3
			AND channel IS NULL
			AND "user" IS NULL))
-- :endmacro

-- :macro channel_or_guild_locale()
-- params: channel_id, guild_id
SELECT COALESCE(
	(
		SELECT locale
		FROM locales
		WHERE channel = $2),
	(
		SELECT locale
		FROM locales
		WHERE
			guild = $1
			AND channel IS NULL
			AND "user" IS NULL))
-- :endmacro

-- :macro guild_locale()
-- params: guild_id
SELECT locale
FROM locales
WHERE
	guild = $1
	AND channel IS NULL
	AND "user" IS NULL
-- :endmacro

-- :macro delete_guild_locale()
-- params: guild_id
DELETE FROM locales
WHERE
	guild = $1
	AND channel IS NULL
	AND "user" IS NULL
-- :endmacro

-- :macro set_guild_locale()
-- params: guild_id, locale
INSERT INTO locales (guild, locale)
VALUES ($1, $2)
-- :endmacro

-- :macro update_channel_locale()
-- params: guild_id, channel_id, locale
INSERT INTO locales (guild, channel, locale)
VALUES ($1, $2, $3)
ON CONFLICT (guild, channel) DO UPDATE
SET locale = EXCLUDED.locale
-- :endmacro

-- :macro update_user_locale()
-- params: user_id, locale
INSERT INTO locales ("user", locale)
VALUES ($1, $2)
ON CONFLICT ("user") DO UPDATE
SET locale = EXCLUDED.locale
-- :endmacro

-- :macro delete_user_locale()
-- params: user_id
DELETE FROM locales
WHERE "user" = $1
-- :endmacro
