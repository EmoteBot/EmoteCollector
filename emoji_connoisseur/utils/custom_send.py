#!/usr/bin/env python3
# encoding: utf-8

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
