{
	'description': 'Emote Collector curates emotes from any server and lets you use them without Nitro.',
	'decay': True,  # whether to enable the deletion of old emotes
	'prefix': 'ec/',

	# your instance of the website code located at https://github.com/EmoteCollector/website
	# if this is left blank, the ec/list command will not advertise the online version of the list.
	'website': 'https://emote-collector.python-for.life',

	# change this user agent if you change the code
	'user_agent': 'EmoteCollectorBot (https://github.com/EmoteCollector/bot)',

	'repo': 'https://github.com/EmoteCollector/bot',

	# related to your instance of https://github.com/EmoteCollector/website
	# if this dict is left empty, the API related commands will be disabled.
	'api': {
		'docs_url': 'https://emote-collector.python-for.life/api/v0/docs',
	},

	# the contents of this file will be sent to the user when they run the "copyright" command
	# as provided by ben_cogs
	'copyright_license_file': 'data/short-license.txt',
	# make this a permanent invite to a guild where users can get help using the bot
	'support_server_invite_code': 'Zujf4K',
	# a user ID of someone to send logs to
	# note: currently nothing is sent except a notification of the bot's guild count being a power of 2
	'send_logs_to': 140516693242937345,

	'ignore_bots': {
		'default': True,
		'overrides': {
			'guilds': frozenset({
				# put guild IDs in here for which you want to override the default behavior
			}),
			'channels': frozenset({
				# put channel IDs in here for which you want to override the default behavior
			}),
		}
	},

	'logs': {
		'emotes': {  # log changes to emotes
			'channel': None,
			'settings': {
				'add': False,  # whether to log whenever an emote is added
				'preserve': True,  # whether to log whenever an emote is preserved
				'unpreserve': True,  # ditto, but for marking an emote as "not preserved" / decayable
				'remove': False,  # whether to log whenever an emote is removed by the author
				'force_remove': True,  # whether to log whenever an emote is removed by a moderator
				'decay': True}}},  # whether to log decayed emotes

	'primary_owner': 140516693242937345,

	'extra_owners': [
		12345],  # User IDs of people authorized to run privileged commands on the bot

	# postgresql connection info
	'database': {
		'user': 'connoisseur',
		'password': 'hunter2',
		'database': 'connoisseur',
		'host': '127.0.0.1',
		'port': 5432},

	'tokens': {
		'discord': 'sek.rit.token',  # get this from https://discordapp.com/developers/applications/me
		'stats': {  # keep these set to None unless your bot is listed on any of these sites
			'bots.discord.pw': None,
			'discordbots.org': None,
			'botsfordiscord.com': None}}


	'success_or_failure_emojis': {False: '❌', True: '✅'}}
