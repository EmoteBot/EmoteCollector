#!/usr/bin/env python3
# encoding: utf-8

import contextlib
import imghdr
import itertools
import io
import logging
import typing

logger = logging.getLogger(__name__)

try:
	import wand.image
except ImportError:
	logger.warn('Failed to import wand.image. Image manipulation functions will be unavailable.')
else:
	import wand.exceptions

from . import errors
from . import size

def resize_until_small(image_data: io.BytesIO) -> io.BytesIO:
	"""If the image_data is bigger than 256KB, resize it until it's not.

	If resizing takes more than 30 seconds, raise asyncio.TimeoutError.
	"""
	# It's important that we only attempt to resize the image when we have to,
	# ie when it exceeds the Discord limit of 256KiB.
	# Apparently some <256KiB images become larger when we attempt to resize them,
	# so resizing sometimes does more harm than good.
	max_resolution = 128  # pixels
	image_size = size(image_data)
	while image_size > 256 * 2**10 and max_resolution >= 32:  # don't resize past 32x32 or 256KiB
		logger.debug('image size too big (%s bytes)', image_size)
		logger.debug('attempting resize to at most%s*%s pixels', max_resolution, max_resolution)

		try:
			image_data = thumbnail(image_data, (max_resolution, max_resolution))
		except wand.exceptions.CoderError:
			raise errors.InvalidImageError

		image_size = size(image_data)
		max_resolution //= 2
	return image_data

def thumbnail(image_data: io.BytesIO, max_size=(128, 128)) -> io.BytesIO:
	"""Resize an image in place to no more than max_size pixels, preserving aspect ratio.

	Return the new image.
	"""
	# Credit to @Liara#0001 (ID 136900814408122368)
	# https://gitlab.com/Pandentia/element-zero/blob/47bc8eeeecc7d353ec66e1ef5235adab98ca9635/element_zero/cogs/emoji.py#L243-247
	with wand.image.Image(blob=image_data) as image:
		new_resolution = scale_resolution((image.width, image.height), max_size)
		image.resize(*new_resolution)
		# we create a new buffer here because there's wand errors otherwise.
		# specific error:
		# MissingDelegateError: no decode delegate for this image format `' @ error/blob.c/BlobToImage/353
		out = io.BytesIO()
		image.save(file=out)

	# allow resizing the original image more than once for memory profiling
	image_data.seek(0)
	# allow reading the resized image data
	out.seek(0)

	return out

def scale_resolution(old_res, new_res):
	"""Resize a resolution, preserving aspect ratio. Returned w,h will be <= new_res"""
	# https://stackoverflow.com/a/6565988

	old_width, old_height = old_res
	new_width, new_height = new_res

	old_ratio = old_width / old_height
	new_ratio = new_width / new_height
	if new_ratio > old_ratio:
		return (old_width * new_height//old_height, new_height)
	return new_width, old_height * new_width//old_width

def is_animated(image_data: bytes):
	"""Return whether the image data is animated, or raise InvalidImageError if it's not an image."""
	type = imghdr.what(None, image_data)
	if type == 'gif':
		return True
	elif type in {'png', 'jpeg'}:
		return False
	else:
		raise errors.InvalidImageError

def main() -> typing.NoReturn:
	"""called in a subprocess so that threads properly die on timeout"""
	import sys

	input = io.BytesIO(sys.stdin.buffer.read())
	try:
		output = resize_until_small(input)
	except errors.InvalidImageError:
		sys.exit(1)
	except BaseException:
		import traceback
		traceback.print_exc()
		sys.exit(2)

	stdout_write = sys.stdout.buffer.write  # getattr optimization

	while True:
		buf = output.read(16 * 1024)
		if not buf:
			break

		stdout_write(buf)

	sys.exit(0)

if __name__ == '__main__':
	main()
