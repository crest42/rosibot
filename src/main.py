"""Signalbot for the Maintenance of "Riesige Rosi" a free and public volunteer run boulder wall in Munich"""

import logging

from rosibot.bot import RosiBot
from rosibot.settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()
bot = RosiBot(settings)

if __name__ == "__main__":
    logger.info("Starting Bot!")
    bot.start()
