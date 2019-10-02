# Contributing to Emote Collector

1. Use tabs for indentation and limit your line length to 120 characters (inclusive, assuming 4-column-sized tabs).
2. If you *can* test your code, please do so [using your own instance of the bot](INSTALLATION.md),
but since installation is so hard, just let me know in the pull request if you haven't tested your changes
and I'll do it for you.
3. Make sure to add docstrings to your functions, and comment them as necessary.
4. New extensions go in [emote_collector/extensions/](emote_collector/extensions/).
New utilities should go in the appropriate file in [emote_collector/utils/](emote_collector/utils/)
or [emote_collector/utils/misc.py](emote_collector/utils/misc.py).

## New database cogs

If a new cog requires access to the database, it should be split into three files:
a database abstraction cog, a discord.py commands cog,
and a [jinja2](https://palletsprojects.com/p/jinja/) template file containing SQL query definitions.

Add its schema definitions (if any) to [emote_collector/sql/schema.sql](emote_collector/sql/schema.sql).

Add its database abstraction cog to emote_collector/extensions/extname/db.py
and queries to a new file in the [sql/](emote_collector/sql/) directory, named after the 
extension that uses it (e.g. extensions/bingo/db.py → sql/bingo.sql).

Finally, the commands cog should use the database cog in the following way:

```py
from ...utils.proxy import ObjectProxy

class Xyz:
	def __init__(self, bot):
		self.bot = bot
		self.db = ObjectProxy(lambda: bot.cogs['XyzDatabase'])
		self.queries = bot.queries('xyz.sql')  # see below
```

The ObjectProxy ensures that the Xyz cog has an up to date reference to XyzDatabase even if XyzDatabase is reloaded.

Your SQL query file should use the following format:

```
-- :macro query1_name()
-- params: parameter 1 description, parameter 2 description, ...
SELECT whatever
FROM tab
WHERE example_code = true
-- :endmacro

-- :macro query2_name()
...
-- :endmacro
```

If you need conditional inclusion, use `varargs` in the macro, like so:

```
-- :macro get_bingo_board()
-- params: user_id
-- optional varargs: with_categories, ...
SELECT
	value
	-- :if 'with_categories' in varargs
	, pos, category
	-- :endif
FROM
	bingo_boards
	-- :if 'with_categories' in varargs
	INNER JOIN bingo_board_categories USING (user_id)
	INNER JOIN bingo_categories USING (category_id)
	-- :endif
WHERE user_id = $1
-- :endmacro
```

You may also use any jinja2 features, including the normal `{% tag %}` and `{{ }}` syntax.

The database abstraction cog should use `emote_collector.utils.connection` and `emote_collector.utils.optional_connection`
like so:

```py
@optional_connection
async def get_xyz(self, user_id):
	async with connection().transaction():
		x1 = await connection().fetchval(self.queries.get_x1(), user_id)
		x2 = await connection().fetchrow(self.queries.get_x2('with_abc'), user_id)
		return await connection().fetchrow(self.queries.get_xyz(), user_id)
```

This ensures that a pool connection is always acquired before get_xyz is called,
unless one has already been acquired in that Task.

If the commands cog needs to call @optional_connection methods more than once, either decorate the command itself:

```py
@commands.command(...)
@optional_connection
async def get_xyz(self, context):
	...
```

Or acquire the connection manually (in case there are other HTTP calls or other expensive IO in the function that should not hold on to a connection):

```py
@commands.command(...)
async def get_xyz(self, context):
	await do_expensive_io()
	async with self.bot.pool.acquire() as conn:
		connection.set(conn)
		await self.db.get_xyz(context.author.id)
		abc = await self.db.get_abc(context.author.id)
	await context.send(abc)  # note that this is done *after* the pool is released
```
