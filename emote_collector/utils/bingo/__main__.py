import asyncio
import json
import sys

from . import EmoteCollectorBingoBoard, render

def main():
	board = EmoteCollectorBingoBoard(**json.load(sys.stdin))
	sys.stdout.buffer.write(render(board))
	sys.exit(0)

if __name__ == '__main__':
	main()
