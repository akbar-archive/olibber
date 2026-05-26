import logging
import sys

from src.bot.webhook import create_app
from src.bot.run import run_bot


app = create_app()


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        run_bot()
    except KeyboardInterrupt:
        print("Bot stopped gracefully ✨")


if __name__ == "__main__":
    main()