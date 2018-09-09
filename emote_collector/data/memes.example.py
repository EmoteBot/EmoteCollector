# this file just contains various text/emote memes
# if data/memes.py doesn't exist, the ec/meme command will be disabled.

{
	# running ec/meme linux would respond with the interjection
	'linux': "I'd just like to interject for a moment…",
	# if a multi line response is given,
	# it will be prefixed with a zero width space
	# for compact mode users
	'multi line': '\n'.join((
		'line1',
		'line2',
		'line3',
	)),
}
