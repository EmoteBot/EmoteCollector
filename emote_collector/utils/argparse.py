#!/usr/bin/env python3
# encoding: utf-8

import argparse

class ArgumentParserError(Exception): pass
class ArgumentParserMessage(ArgumentParserError): pass

class ArgumentParser(argparse.ArgumentParser):
	def _print_message(self, message, *_):
		raise ArgumentParserMessage(f'```\n{message}```')

	def error(self, message):
		raise ArgumentParserError(message)
