import json
import sys

from . import EmoteCollectorBingoBoard, render

board = EmoteCollectorBingoBoard(**json.load(sys.stdin))
sys.stdout.buffer.write(render(board))
