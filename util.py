#!/usr/bin/env python
# encoding: utf-8

from __future__ import print_function

from sys import stderr as _stderr


def log(*args, **kwargs):
	kwargs['file'] = _stderr
	print(*args, **kwargs)
