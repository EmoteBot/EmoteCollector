import contextlib
import imghdr
import io
import logging

logger = logging.getLogger(__name__)

try:
	from wand.image import Image
except ImportError:
	logger.warn('Failed to import wand.image. Image manipulation functions will be unavailable.')

from . import errors

def resize_until_small(image_data: io.BytesIO):
	"""If the image_data is bigger than 256KB, resize it until it's not"""
	# It's important that we only attempt to resize the image when we have to,
	# ie when it exceeds the Discord limit of 256KiB.
	# Apparently some <256KiB images become larger when we attempt to resize them,
	# so resizing sometimes does more harm than good.
	max_resolution = 128  # pixels
	image_size = size(image_data)
	while image_size > 256 * 2**10 and max_resolution >= 32:  # don't resize past 32x32 or 256KiB
		logger.debug('image size too big (%s bytes)', image_size)
		logger.debug('attempting resize to %s*%s pixels', max_resolution, max_resolution)
		image_data = thumbnail(image_data, (max_resolution, max_resolution))
		image_size = size(image_data)
		max_resolution //= 2
	return image_data

def size(data: io.BytesIO):
	"""return the size, in bytes, of the data a BytesIO object represents"""
	with preserve_position(data):
		data.seek(0, io.SEEK_END)
		return data.tell()

def thumbnail(image_data: io.BytesIO, max_size=(128, 128)):
	"""Resize an image in place to no more than max_size pixels, preserving aspect ratio."""
	# Credit to @Liara#0001 (ID 136900814408122368)
	# https://gitlab.com/Pandentia/element-zero/blob/47bc8eeeecc7d353ec66e1ef5235adab98ca9635/element_zero/cogs/emoji.py#L243-247
	image = Image(blob=image_data)
	image.resize(*scale_resolution((image.width, image.height), max_size))
	# we create a new buffer here because there's wand errors otherwise.
	# specific error:
	# MissingDelegateError: no decode delegate for this image format `' @ error/blob.c/BlobToImage/353
	out = io.BytesIO()
	image.save(file=out)
	out.seek(0)
	return out

def scale_resolution(old_res, new_res):
	# https://stackoverflow.com/a/6565988
	"""Resize a resolution, preserving aspect ratio. Returned w,h will be <= new_res"""
	old_width, old_height = old_res
	new_width, new_height = new_res
	old_ratio = old_width / old_height
	new_ratio = new_width / new_height
	if new_ratio > old_ratio:
		return (old_width * new_height//old_height, new_height)
	return new_width, old_height * new_width//old_width

class preserve_position(contextlib.AbstractContextManager):
	def __init__(self, fp):
		self.fp = fp
		self.old_pos = fp.tell()

	def __exit__(self, *excinfo):
		self.fp.seek(self.old_pos)

def is_animated(image_data: bytes):
	"""Return whether the image data is animated, or raise InvalidImageError if it's not an image."""
	type = imghdr.what(None, image_data)
	if type == 'gif':
		return True
	elif type in ('png', 'jpeg'):
		return False
	else:
		raise errors.InvalidImageError
