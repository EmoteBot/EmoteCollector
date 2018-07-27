SET TIME ZONE UTC;

CREATE TABLE IF NOT EXISTS emote(
	name VARCHAR(32) NOT NULL,
	id BIGINT NOT NULL UNIQUE,
	author BIGINT NOT NULL,
	animated BOOLEAN DEFAULT FALSE,
	description VARCHAR(280),
	created TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
	modified TIMESTAMP WITH TIME ZONE,
	preserve BOOLEAN DEFAULT FALSE);

CREATE UNIQUE INDEX IF NOT EXISTS emote_lower_idx ON emote (LOWER(name));
CREATE INDEX IF NOT EXISTS emote_author_idx ON emote (author);

-- https://stackoverflow.com/a/26284695/1378440
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
	IF row(NEW.*) IS DISTINCT FROM row(OLD.*) THEN
		NEW.modified = CURRENT_TIMESTAMP;
		RETURN NEW;
	ELSE
		RETURN OLD; END IF; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_emote_modtime ON emote;

CREATE TRIGGER update_emote_modtime
BEFORE UPDATE ON emote
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

DROP TABLE IF EXISTS blacklists;

CREATE TABLE IF NOT EXISTS user_opt(
	id BIGINT NOT NULL UNIQUE,
	state BOOLEAN,
	blacklist_reason VARCHAR(500));

CREATE TABLE IF NOT EXISTS guild_opt(
	id BIGINT NOT NULL UNIQUE,
	state BOOLEAN NOT NULL);

CREATE TABLE IF NOT EXISTS emote_usage_history(
	id BIGINT,
	time TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP));

CREATE INDEX IF NOT EXISTS emote_usage_history_id_idx ON emote_usage_history (id);

-- https://stackoverflow.com/a/25499662
ALTER TABLE emote_usage_history
	DROP CONSTRAINT IF EXISTS emote_usage_history_id_fkey,
	ADD CONSTRAINT emote_usage_history_id_fkey FOREIGN KEY (id)
		REFERENCES emote (id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS emote_usage_history_time_idx ON emote_usage_history (time);

-- utility funcs --

CREATE OR REPLACE FUNCTION str_contains(text, text) RETURNS bool AS $$
BEGIN
	-- strpos(haystack, needle)
	-- we want str_contains(needle, haystack)
	RETURN strpos($2, $1) > 0; END;
$$ LANGUAGE plpgsql;

-- old stuff --

DROP INDEX IF EXISTS emojis_lower_idx;
DROP INDEX IF EXISTS emojis_author_idx;

DROP TRIGGER IF EXISTS update_emoji_modtime ON emote;
