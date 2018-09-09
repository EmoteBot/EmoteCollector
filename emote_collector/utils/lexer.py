#!/usr/bin/env python3
# encoding: utf-8

import ply.lex

tokens = (
	"CODE",
	"ESCAPED_EMOTE",
	"CUSTOM_EMOTE",
	"EMOTE",
	"TEXT",
)

"""Matches code blocks, which should be ignored."""
t_CODE = '(?su)(?P<code>`{1,3}).+?(?P=code)'

"""Matches \:foo: and \;foo;, allowing one to prevent the emote auto response for one emote."""
# we don't need to match :foo\:, since "foo\" is not a valid emote name anyway
t_ESCAPED_EMOTE = r'(?a)\\(?P<colon>:|;)\w{2,32}(?P=colon)'

"""Matches only custom server emotes."""
t_CUSTOM_EMOTE = r'(?a)<(?P<animated>a?):(?P<name>\w{2,32}):(?P<id>\d{17,})>'

"""Matches :foo: and ;foo; but not :foo;. Used for emotes in text."""
t_EMOTE = r'(?a)(?P<colon>:|;)(?P<name>\w{2,32})(?P=colon)'

t_TEXT = r'(?s).'

def t_error(t):
	raise SyntaxError(f'Unknown text "{t.value}"')

# it is required that ply.lex.lex be run in the context of this module
# so we can't just say "lexer = ply.lex.lex" cause that'll run lex()
# in the context of the caller's module
new = lambda: ply.lex.lex()

def main():
	import textwrap

	lexer = new()

	test = textwrap.dedent("""
		You're mom gay
		haha lol xd
		:hahaYes: :notlikeblob: ;cruz;
		\:thonk: `:speedtest:`
		<:foo:123456789123456789> <a:foo:123456789123456789>
		```
		:congaparrot:;congaparrot;:congaparrot:
		` foo bar
		<:foo:123456789123456789> <a:foo:123456789123456789>
		`` baz ``
		```
	""")
	lexer.input(test)

	print(test)

	for toke1 in iter(lexer.token, None):
		print(f'{toke1.type}: {toke1.value!r}')

	ply.lex.runmain()

if __name__ == '__main__':
	main()
