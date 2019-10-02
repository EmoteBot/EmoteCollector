-- :macro upsert_board()
-- params: user_id, value, categories, marks
INSERT INTO bingo_boards (user_id, value, categories, marks)
VALUES ($1, $2, $3, $4)
ON CONFLICT (user_id) DO UPDATE SET
	value = EXCLUDED.value,
	categories = EXCLUDED.categories,
	marks = EXCLUDED.marks
RETURNING value, categories, marks
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
