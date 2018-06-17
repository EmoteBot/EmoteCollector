from discord.ext.commands import CommandError


class ConnoisseurError(CommandError):
	"""Generic error with the bot. This can be used to catch all bot errors."""
	pass


class HTTPException(ConnoisseurError):
	"""The server did not respond with an OK status code."""
	def __init__(self, status):
		super().__init__(f'URL error: server returned error code {status}')


class EmoteExistsError(ConnoisseurError):
	"""An emote with that name already exists"""
	def __init__(self, name):
		super().__init__(f'An emote called `{name}` already exists in my database.')


class EmoteNotFoundError(ConnoisseurError):
	"""An emote with that name was not found"""
	def __init__(self, name):
		super().__init__(f'An emote called `{name}` does not exist in my database.')


class InvalidImageError(ConnoisseurError):
	"""The image is not a GIF, PNG, or JPG"""
	def __init__(self):
		super().__init__('The image supplied was not a GIF, PNG, or JPG.')


class NoMoreSlotsError(ConnoisseurError):
	"""Raised in the rare case that all slots of a particular type (static/animated) are full
	if this happens, make a new Emoji Backend account, create 100 more guilds, and add the bot
	to all of these guilds.
	"""
	def __init__(self):
		super().__init__('No more backend slots available.')


class PermissionDeniedError(ConnoisseurError):
	"""Raised when a user tries to modify an emote they don't own"""
	def __init__(self, name):
		super().__init__(f"You're not authorized to modify `{name}`.")


class DiscordError(Exception):
	"""Usually raised when the client cache is being baka"""
	def __init__(self):
		super().__init__('Discord seems to be having issues right now, please try again later.')
