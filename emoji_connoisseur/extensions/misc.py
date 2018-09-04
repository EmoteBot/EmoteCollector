import os.path

from ben_cogs.misc import Misc

from .. import BASE_DIR

class Misc(Misc):
	def __init__(self, bot):
		self.bot = bot
		with open(os.path.join(BASE_DIR, self.bot.config['copyright_license_file'])) as f:
			self.license_message = f.read()

def setup(bot):
	bot.add_cog(Misc(bot))
