-- Emote Collector collects emotes from other servers for use by people without Nitro
-- Copyright © 2019 lambda--0987
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

CREATE TABLE emotes(
	name VARCHAR(32) NOT NULL,
	id BIGINT PRIMARY KEY,
	created TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
	preserve BOOLEAN DEFAULT FALSE);

CREATE TABLE emote_usage_history(
	id BIGINT,
	time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP);

INSERT INTO emotes
	(name, id, created, preserve)
VALUES
	('donotdecay1', 1, CURRENT_TIMESTAMP, false),  -- new without usage
	('donotdecay2', 2, CURRENT_TIMESTAMP, false),  -- new with usage
	('donotdecay3', 3, '1970-01-01',      false),  -- old with usage
	('donotdecay4', 4, '1970-01-01',      true),  -- old without usage but preserved
	('donotdecay5', 5, '1970-01-01',      true),  -- old with little (1) usage but preserved
	('decay1',      6, '1970-01-01',      false),  -- old without usage
	('decay2',      7, '1970-01-01',      false);  -- old with some (3) usage but a long time ago


INSERT INTO emote_usage_history
  (id)
VALUES
  (2),
  (2),
  (2),

  (3),
  (3),
  (3),

  (5);

INSERT INTO emote_usage_history
  (id, time)
VALUES
  (7, '1970-01-01'),
  (7, '1970-01-01'),
  (7, '1970-01-01');

SELECT e.name, e.id, COUNT(euh.id) AS usage
FROM emotes AS e
LEFT JOIN emote_usage_history AS euh
	ON euh.id = e.id
	AND time > CURRENT_TIMESTAMP - INTERVAL '4 weeks'
WHERE created < CURRENT_TIMESTAMP - INTERVAL '4 weeks'
      AND NOT preserve
GROUP BY e.id
HAVING COUNT(euh.id) < 3;
