# Contributing to Emote Collector

For now, this is just a list of things to keep in mind when hacking on the bot.

1. Use tabs for indentation and keep your lines less than 110 characters long.
2. If you *can* test your code, please do so [using your own instance of the bot](INSTALLATION.md),
but since installation is so hard, just let me know in the pull request if you haven't tested your changes
and I'll do it for you.
3. Any helper functions you create for just one command should go below that command,
in the order that they're used in the command. Any helper functions for *those* helper functions should
follow the same rule. So,
```py
@commands.command()
async def foo(self, context):
	await bar()
	baz()

async def bar(self):
	return quux(self.user.id)

def quux(self, id):
	return id+1

def baz(self):
	print('hi')
```
4. Make sure to add docstrings to your functions, and comment them as necessary.
