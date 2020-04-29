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

import asyncio
import base64
import contextlib
import io
import logging
import signal
import sys
import typing

logger = logging.getLogger(__name__)

try:
	import wand.image
except (ImportError, OSError):
	logger.warning('Failed to import wand.image. Image manipulation functions will be unavailable.')
else:
	import wand.exceptions

from . import errors
from . import size

MAX_EMOTE_SIZE = 256 * 1024

def resize_until_small(image_data: io.BytesIO) -> None:
	"""If the image_data is bigger than the maximum allowed by discord, resize it until it's not."""
	# It's important that we only attempt to resize the image when we have to, ie when it exceeds the Discord limit.
	# Apparently some small images become larger than the size limit when we attempt to resize them,
	# so resizing sometimes does more harm than good.
	max_resolution = 128  # pixels
	image_size = size(image_data)
	if image_size <= MAX_EMOTE_SIZE:
		return

	try:
		with wand.image.Image(blob=image_data) as original_image:
			while True:
				logger.debug('image size too big (%s bytes)', image_size)
				logger.debug('attempting resize to at most%s×%s pixels', max_resolution, max_resolution)

				with original_image.clone() as resized:
					# resize the image while preserving aspect ratio
					resized.transform(resize=f'{max_resolution}x{max_resolution}')
					image_size = len(resized.make_blob())
					if image_size <= MAX_EMOTE_SIZE or max_resolution < 32:  # don't resize past the max or 32×32
						image_data.truncate(0)
						image_data.seek(0)
						resized.save(file=image_data)
						image_data.seek(0)
						break

				max_resolution //= 2
	except wand.exceptions.CoderError:
		raise errors.InvalidImageError

def is_animated(image_data: bytes):
	"""Return whether the image data is animated, or raise InvalidImageError if it's not an image.
	Note: unlike mime_type_for_image(), this function requires the *entire* image.
	"""
	type = mime_type_for_image(image_data)
	if type == 'image/gif':
		return is_animated_gif(image_data)
	elif type in {'image/png', 'image/jpeg', 'image/webp'}:
		return False
	else:
		raise errors.InvalidImageError

def is_animated_gif(gif_image: bytes):
	with wand.image.Image(blob=gif_image) as img:
		return len(wand.sequence.Sequence(img)) > 1

"""The fewest bytes needed to identify the type of an image."""
MINIMUM_BYTES_NEEDED = 12

def mime_type_for_image(data):
	if data.startswith(b'\x89PNG\r\n\x1a\n'):
		return 'image/png'
	if data.startswith(b'\xFF\xD8') and data[6:10] in (b'JFIF', b'Exif'):
		return 'image/jpeg'
	if data.startswith((b'GIF87a', b'GIF89a')):
		return 'image/gif'
	if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
		return 'image/webp'
	raise errors.InvalidImageError

def image_to_base64_url(data):
	fmt = 'data:{mime};base64,{data}'
	mime = mime_type_for_image(data)
	b64 = base64.b64encode(data).decode('ascii')
	return fmt.format(mime=mime, data=b64)

def main() -> typing.NoReturn:
	"""resize an image from stdin and write the resized version to stdout."""
	data = io.BytesIO(sys.stdin.buffer.read())
	try:
		resize_until_small(data)
	except errors.InvalidImageError:
		# 2 is used because 1 is already used by python's default error handler
		sys.exit(2)

	stdout_write = sys.stdout.buffer.write  # getattr optimization

	for buf in iter(lambda: data.read(16 * 1024), b''):
		stdout_write(buf)

	sys.exit(0)

async def resize_in_subprocess(image_data: bytes):
	if len(image_data) <= MAX_EMOTE_SIZE:
		return image_data

	proc = await asyncio.create_subprocess_exec(
		sys.executable, '-m', __name__,

		stdin=asyncio.subprocess.PIPE,
		stdout=asyncio.subprocess.PIPE,
		stderr=asyncio.subprocess.PIPE)

	try:
		image_data, err = await asyncio.wait_for(proc.communicate(image_data), timeout=30)
	except asyncio.TimeoutError:
		proc.send_signal(signal.SIGINT)
		raise errors.ImageResizeTimeoutError
	else:
		if proc.returncode == 2:
			raise errors.InvalidImageError
		if proc.returncode != 0:
			raise RuntimeError(err.decode('utf-8') + f'Return code: {proc.returncode}')

	return image_data

if __name__ == '__main__':
	main()
