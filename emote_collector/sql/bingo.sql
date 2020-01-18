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

-- :macro get_categories()
-- params: num_categories
SELECT category_id, category
FROM bingo_categories
-- it is not assumed that there will be very many categories, so sorting the entire table is fine
ORDER BY RANDOM()
LIMIT $1
-- :endmacro

-- :macro delete_board()
-- params: user_id
DELETE FROM bingo_boards
WHERE user_id = $1
-- :endmacro

-- :macro get_board_value()
-- params: user_id
SELECT value
FROM bingo_boards
WHERE user_id = $1
-- :endmacro

-- :macro set_board_value()
-- params: user_id, value
INSERT INTO bingo_boards (user_id, value)
VALUES ($1, $2)
ON CONFLICT (user_id) DO UPDATE SET
	value = EXCLUDED.value
-- :endmacro

-- :macro get_board_categories()
-- params: user_id
SELECT category
FROM
	bingo_boards
	INNER JOIN bingo_board_categories USING (user_id)
	INNER JOIN bingo_categories USING (category_id)
WHERE user_id = $1
ORDER BY pos
-- :endmacro

-- :macro set_board_category()
-- params: user_id, pos, category
INSERT INTO bingo_board_categories (user_id, pos, category_id)
VALUES ($1, $2, (SELECT category_id FROM bingo_categories WHERE category = $3))
-- :endmacro

-- :macro get_board_marks()
-- params: user_id
SELECT
	pos,
	COALESCE(deleted.nsfw, emotes.nsfw) AS nsfw,
	COALESCE(deleted.name, emotes.name) AS name,
	COALESCE(marks.deleted_emote_id, marks.emote_id) AS id,
	COALESCE(deleted.animated, emotes.animated) AS animated
FROM
	bingo_board_marks AS marks
	LEFT JOIN bingo_deleted_emotes AS deleted USING (deleted_emote_id)
	LEFT JOIN emotes ON (marks.emote_id = emotes.id)
WHERE user_id = $1
ORDER BY pos
-- :endmacro

-- :macro set_board_mark()
-- params: user_id, pos, nsfw, name, emote_id, animated
-- required transaction isolation level: repeatable read
CALL bingo_mark($1, $2, $3, $4, $5, $6);
-- :endmacro

-- :macro delete_board_mark()
-- params: user_id, pos
DELETE FROM bingo_board_marks
WHERE (user_id, pos) = ($1, $2)
-- :endmacro

-- :macro delete_board_marks_by_mask()
-- params: user_id, mask
UPDATE bingo_boards
SET value = value & ~$2::INTEGER
WHERE user_id = $1
-- :endmacro

-- :macro add_board_marks_by_mask()
-- params: user_id, mask
UPDATE bingo_boards
SET value = value | $2::INTEGER
WHERE user_id = $1
-- :endmacro
