--- CACHE SYNCHRONIZATION

-- :query delete_all_guilds
DELETE FROM _guilds
-- :endquery

-- :query add_guild
-- params: guild_id
INSERT INTO _guilds (id)
VALUES ($1)
ON CONFLICT DO NOTHING
-- :endquery

-- :query delete_guild
-- params: guild_id
DELETE FROM _guilds
WHERE id = $1
-- :endquery

-- :query delete_all_moderators
DELETE FROM moderators
-- :endquery

-- :query add_moderator
-- params: moderator_id
INSERT INTO moderators (id)
VALUES ($1)
ON CONFLICT (id) DO NOTHING
-- :endquery

-- :query delete_moderator
-- params: moderator_id
DELETE FROM moderators
WHERE id = $1
-- :endquery

--- INFORMATIONAL

-- :macro free_guild(animated)
SELECT id
FROM guilds
WHERE {{ 'animated' if animated else 'static' }}_usage < 50
ORDER BY random()
LIMIT 1
-- :endmacro

-- :query count
SELECT
	COUNT(*) FILTER (WHERE NOT animated) AS static,
	COUNT(*) FILTER (WHERE animated) AS animated,
	COUNT(*) FILTER (WHERE nsfw != 'SFW') AS nsfw,
	COUNT(*) AS total
FROM emotes
-- :endquery

-- :query get_emote
-- params: name
SELECT *
FROM emotes
WHERE LOWER(name) = LOWER($1)
-- :endquery

-- :query get_emote_usage
-- params: id, cutoff_time
SELECT COUNT(*)
FROM emote_usage_history
WHERE id = $1
  AND time > $2
-- :endquery

-- :query get_reply_message
-- params: invoking_message_id
SELECT type, reply_message
FROM replies
WHERE invoking_message = $1
-- :endquery

--- ITERATORS

-- :macro all_emotes_keyset(sort_order, filter_author=False)
SELECT *
FROM emotes
WHERE nsfw = ANY ($1)
-- :set argc = 2
-- :if sort_order is defined
	AND LOWER(name) {{ '>' if sort_order == 'ASC' else '<' }} LOWER(${{ argc }})
	-- :set argc = argc + 1
-- :endif
-- :if filter_author
	AND author = ${{ argc }}
	-- :set argc = argc + 1
-- :endif
ORDER BY LOWER(name) {{ sort_order }} LIMIT 100
-- :endmacro

-- :set emote_usage_history_prelude
SELECT e.*, COUNT(euh.id) AS usage
FROM
	emotes AS e
	LEFT JOIN emote_usage_history AS euh
		ON euh.id = e.id
		AND euh.time > $1
-- :endset

-- :macro popular_emotes(filter_author=False)
-- params: cutoff_time, limit, allowed_nsfw_types, author_id (optional)
{{ emote_usage_history_prelude }}
WHERE
	nsfw = ANY ($3)
	{% if filter_author %}AND author = $4{% endif %}
GROUP BY e.id
ORDER BY usage DESC, LOWER(e.name)
LIMIT $2
-- :endmacro

-- :query search
-- params: query, allowed_nsfw_types
SELECT *
FROM emotes
WHERE name % $1
AND nsfw = ANY ($2)
ORDER BY similarity(name, $1) DESC, LOWER(name)
LIMIT 100
-- :endquery

-- :query decayable_emotes
-- params: cutoff_time, usage_threshold
{{ emote_usage_history_prelude }}
WHERE
	created < $1
	AND NOT preserve
GROUP BY e.id
HAVING COUNT(euh.id) < $2
-- :endquery

