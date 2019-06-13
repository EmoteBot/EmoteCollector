SET TIME ZONE UTC;

CREATE TYPE nsfw AS ENUM ('SFW', 'SELF_NSFW', 'MOD_NSFW');

CREATE TABLE _guilds(
	id BIGINT PRIMARY KEY);

CREATE TABLE emotes(
	name VARCHAR(32) NOT NULL,
	id BIGINT PRIMARY KEY,
	author BIGINT NOT NULL,
	animated BOOLEAN NOT NULL DEFAULT FALSE,
	description VARCHAR(280),
	created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
	modified TIMESTAMP WITH TIME ZONE,
	preserve BOOLEAN NOT NULL DEFAULT FALSE,
	guild BIGINT NOT NULL REFERENCES _guilds ON DELETE CASCADE,
	nsfw nsfw NOT NULL DEFAULT 'SFW');

CREATE UNIQUE INDEX emotes_lower_idx ON emotes (LOWER(name));
CREATE INDEX emotes_name_trgm_idx ON emotes USING GIN (name gin_trgm_ops);
CREATE INDEX emotes_author_idx ON emotes (author);
CREATE INDEX emotes_created_idx ON emotes (created) WHERE NOT preserve;
CREATE INDEX emotes_nsfw_idx ON emotes (nsfw);

CREATE VIEW guilds AS
	-- thanks to ysch on freenode/#postgresql for helping me with this query
	SELECT g.id,
	COUNT(e.guild) AS usage,
	COUNT(e.guild) FILTER (WHERE NOT e.animated) AS static_usage,
	COUNT(e.guild) FILTER (WHERE e.animated) AS animated_usage
	FROM _guilds AS g
	LEFT JOIN emotes AS e
		ON e.guild = g.id
	GROUP BY g.id;

-- https://stackoverflow.com/a/26284695/1378440
CREATE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
	IF row(NEW.*) IS DISTINCT FROM row(OLD.*) THEN
		NEW.modified = CURRENT_TIMESTAMP;
		RETURN NEW;
	ELSE
		RETURN OLD; END IF; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_emote_modtime
BEFORE UPDATE ON emotes
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

CREATE TABLE user_opt(
	id BIGINT NOT NULL UNIQUE,
	state BOOLEAN,
	blacklist_reason VARCHAR(500));

CREATE TABLE guild_opt(
	id BIGINT NOT NULL UNIQUE,
	state BOOLEAN NOT NULL);

CREATE TABLE moderators(
	id BIGINT PRIMARY KEY);

CREATE TABLE emote_usage_history(
	id BIGINT NOT NULL REFERENCES emotes ON DELETE CASCADE,
	time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP));

CREATE INDEX emote_usage_history_id_idx ON emote_usage_history (id);
CREATE INDEX emote_usage_history_time_idx ON emote_usage_history (time);

CREATE TABLE api_tokens(
	id BIGINT PRIMARY KEY,
	secret BYTEA NOT NULL);

CREATE INDEX api_token_secret_idx ON api_tokens (secret);
CREATE INDEX api_token_id_secret_idx ON api_tokens (id, secret);

CREATE TABLE locales(
	guild BIGINT,
	channel BIGINT,
	"user" BIGINT UNIQUE,
	locale VARCHAR(32) NOT NULL,

	CHECK (
		guild IS NOT NULL AND channel IS NULL AND "user" IS NULL
		OR guild IS NOT NULL AND channel IS NOT NULL
		OR channel IS NOT NULL
		OR "user" IS NOT NULL));

CREATE INDEX locales_guild_idx ON locales (guild);
CREATE INDEX locales_channel_idx ON locales (channel);
CREATE INDEX locales_user_idx ON locales ("user");

CREATE UNIQUE INDEX locales_guild_channel_unique_index ON locales (guild, channel);

CREATE TYPE message_reply_type AS ENUM ('AUTO', 'QUOTE');

CREATE TABLE replies(
	invoking_message BIGINT PRIMARY KEY,
	type message_reply_type NOT NULL,
	reply_message BIGINT NOT NULL);
