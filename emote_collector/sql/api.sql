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

-- :macro existing_token()
-- params: user_id
SELECT secret
FROM api_tokens
WHERE id = $1
-- :endmacro

-- :macro new_token()
-- params: user_id, secret
INSERT INTO api_tokens (id, secret)
VALUES ($1, $2)
-- :endmacro

-- :macro delete_token()
-- params: user_id
DELETE FROM api_tokens
WHERE id = $1
-- :endmacro
