import asyncio

from discord.ext.commands import CommandError

class ConnoisseurError(CommandError):
	"""Generic error with the bot. This can be used to catch all bot errors."""
	pass

class BlacklistedError(ConnoisseurError):
	"""The user tried to use a command but they were blacklisted."""
	def __init__(self, prefix, reason):
		super().__init__(_(
			'Sorry, you have been blacklisted with the reason `{reason}`. '
			'To appeal, please join the support server with `{prefix}support`.').format(**locals()))

class HTTPException(ConnoisseurError):
	"""The server did not respond with an OK status code."""
	def __init__(self, status):
		self.status = status
		super().__init__(_('URL error: server returned error code {status}').format(**locals()))

class InvalidImageError(ConnoisseurError):
	"""The image is not a GIF, PNG, or JPG"""
	def __init__(self):
		super().__init__(_('The image supplied was not a GIF, PNG, or JPG.'))

class URLTimeoutError(ConnoisseurError, asyncio.TimeoutError):
	"""Retrieving the image took too long."""
	def __init__(self):
		super().__init__(_('Error: Retrieving the image took too long.'))

class ImageResizeTimeoutError(ConnoisseurError, asyncio.TimeoutError):
	"""Resizing the image took too long."""
	def __init__(self):
		super().__init__(_('Error: Resizing the image took too long.'))

class EmoteError(ConnoisseurError):
	"""Abstract error while trying to modify an emote"""
	def __init__(self, message, name=None):
		self.name = name
		super().__init__(message.format(name=self.name))

class EmoteExistsError(EmoteError):
	"""An emote with that name already exists"""
	def __init__(self, emote):
		self.emote = emote
		super().__init__(_('An emote called `{name}` already exists in my database.'), self.emote.name)

class EmoteNotFoundError(EmoteError):
	"""An emote with that name was not found"""
	def __init__(self, name):
		super().__init__(_('An emote called `{name}` does not exist in my database.'), name)

class PermissionDeniedError(EmoteError):
	"""Raised when a user tries to modify an emote they don't own"""
	def __init__(self, name):
		super().__init__(_("You're not authorized to modify `{name}`."), name)

class EmoteDescriptionTooLongError(EmoteError):
	"""Raised when a user tries to set a description that's too long"""
	def __init__(self, name, actual_length, max_length):
		self.actual_length = actual_length
		self.limit = limit = self.max_length = max_length
		super().__init__(_(
			'That description is too long. The limit is {limit}.').format(**locals()))

class NoMoreSlotsError(ConnoisseurError):
	"""Raised in the rare case that all slots of a particular type (static/animated) are full
	if this happens, make a new Emoji Backend account, create 100 more guilds, and add the bot
	to all of these guilds.
	"""
	def __init__(self):
		super().__init__(_('No more room to store emotes.'))

class DiscordError(Exception):
	"""Usually raised when the client cache is being baka"""
	def __init__(self):
		super().__init__(_('Discord seems to be having issues right now, please try again later.'))
