-- :query upsert_board
-- params: user_id, value, categories, marks
INSERT INTO bingo_boards (user_id, value, categories, marks)
VALUES ($1, $2, $3, $4)
ON CONFLICT (user_id) DO UPDATE SET
	value = EXCLUDED.value,
	categories = EXCLUDED.categories,
	marks = EXCLUDED.marks
RETURNING value, categories, marks
-- :endquery

-- :query get_board
-- params: user_id
SELECT value, categories, marks
FROM bingo_boards
WHERE user_id = $1
-- :endquery
