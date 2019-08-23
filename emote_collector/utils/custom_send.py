# Emote Collector collects emotes from other servers for use by people without Nitro
# Copyright © 2018–2019 lambda#0987
#
# Emote Collector is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Emote Collector is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Emote Collector. If not, see <https://www.gnu.org/licenses/>.

import functools

import discord.abc

# original at https://gist.github.com/ded2d8b33f29a449d4eaed0f77880adf

_hooks = []
_patched = False
_old_send = discord.abc.Messageable.send

def global_message_send_hook(func):
	_hooks.append(func)
	_monkey_patch()
	# allow this to be used as a decorator
	return func

register = global_message_send_hook

unregister = _hooks.remove

def restore():
	global _patched

	_hooks.clear()
	discord.abc.Messageable.send = _old_send
	_patched = False

def _monkey_patch():
	global _patched

	if _patched:
		return

	@functools.wraps(_old_send)
	async def send(self, *args, **kwargs):
		# old_send is not a bound method.
		# "bind" it to self, so that the user doesnt have to pass in self manually
		bound_old_send = functools.partial(_old_send, self)

		for hook in _hooks:
			# allow the user to prevent default send behavior
			# by returning False
			# pass in old_send so that the user can still send
			# using the original behavior
			should_continue, *result = await hook(bound_old_send, *args, **kwargs)
			if not should_continue:
				return result[0]

		return await _old_send(self, *args, **kwargs)

	discord.abc.Messageable.send = send
	_patched = True
