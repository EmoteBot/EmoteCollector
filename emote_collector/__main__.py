import os.path

from . import EmoteCollector, BASE_DIR
from . import utils

config = utils.load_json_compat(BASE_DIR / 'data' / 'config.py')

bot = EmoteCollector(config=config)
bot.run()
