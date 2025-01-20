"""Signalbot for the Maintenance of "Riesige Rosi" a free and public volunteer run boulder wall in Munich"""

from typing import Tuple

import os
import logging
import asyncio
import datetime
from pathlib import Path

from signalbot import SignalBot, Command, Context
from pydantic_settings import BaseSettings, SettingsConfigDict

BOT_MENTION_COMMAND = "!"
MONDAY = 0
FRIDAY = 5
LOCK_FILE_PATH = "/tmp"
WEEKLY_REMINDER_MESSAGE = "Hallo! Es ist wieder Montag und die wöchentliche Wartung für {KW} der Rosi steht an. Wenn du lust hast bei der Wartung zu unterstützen antworte auf diese Nachricht mit !erledigt. Wenn du Hilfe benötigst schreibe !hilfe"  # pylint: disable=line-too-long
WEEKLY_REMINDER_MESSAGE_FRIDAY = "Hallo! Es ist Freitag und die Wartung der Rosi steht noch aus für diese Woche. Wenn du lust hast bei der Wartung zu unterstützen antworte auf diese Nachricht mit !erledigt. Wenn du Hilfe benötigst schreibe !hilfe"  # pylint: disable=line-too-long
MAINTENANCE_HELPER_MESSAGE = "Was genau bei einer Wartung getan werden muss steht in der Gruppenbeschreibung. Bei Fragen wende dich bitte an Teresa, Robin oder fragt in diese Gruppe"  # pylint: disable=line-too-long
MAINTENANCE_DONE_MESSAGE = "Danke für deine Unterstützung. Vergiss bitte nicht dich in der ausgelegten Liste im lager der Rosi zu unterschreiben und die Fotos auf den google drive zu laden"  # pylint: disable=line-too-long
MAINTENANCE_ALREADY_DONE_MESSAGE = "Danke für deine Unterstützung. Die Wartung für diese Woche wurde bereits erledigt."  # pylint: disable=line-too-long
ROSIBOT_PREFIX = "[ROSIBOT]: "


def get_weekly_lock_file() -> Tuple[int, int, str]:
    """Returns some ad-hoc date information used to handle file based locking

    Returns:
        Tuple[int, int, str]: Tuple of weekday (0-6), week number (0-42) and a filename used for weekly locking
    """
    today = datetime.datetime.today()
    file = f"{LOCK_FILE_PATH}/rosibot_{today.year}_{today.isocalendar().week}"
    return (today.weekday(), today.isocalendar().week, file)


class Settings(BaseSettings):
    """Pydantic-settings class used to control signal specific settings"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    signal_service: str
    phone_number: str
    signal_group_id: str


logger = logging.getLogger("rosibot")
logger.setLevel(logging.DEBUG)
settings = Settings()
bot = SignalBot(
    {"signal_service": settings.signal_service, "phone_number": settings.phone_number}
)


async def send(message: str) -> None:
    """Send a message to group defined in the settings. Prefixes all messages with a BOT identifier"""
    await bot.send(settings.signal_group_id, ROSIBOT_PREFIX + message)


class RosiBot:
    """RosiBot main implementation"""

    @classmethod
    async def handle(cls, text: str) -> None:
        """Bot Command handler. Handles any bot command passed to it.

        Valid Bot commands are supposed to look like: "!<command>"

        Args:
            text (str): Bot command
        """
        if text.startswith("!"):
            logger.debug(f"Received Bot command: {text}")
            if text.startswith("!hilfe"):
                await send(MAINTENANCE_HELPER_MESSAGE)
            if text.startswith("!erledigt"):
                _, week, file = get_weekly_lock_file()
                with open(file, "a", encoding="utf-8") as f:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    if size <= 1:
                        logger.debug(
                            f"Weekly maintenance for {week} done. Updating Log file"
                        )
                        f.write("Done")
                        await send(MAINTENANCE_DONE_MESSAGE)
                    else:
                        logger.debug(
                            f"Weekly maintenance for {week} already done. Do nothing"
                        )
                        await send(MAINTENANCE_ALREADY_DONE_MESSAGE)
        else:
            logger.error(f"Invalid bot command {text}. Do nothing")


class BotMention(Command):
    """Handle class for bot commands"""

    async def handle(self, context: Context) -> None:
        """Main handler function for the bot.
        This function checks if a command is a bot command and handles it accordingly.

        Args:
            c (Context): Message context as send by signalbot
        """
        if context.message.text.startswith(BOT_MENTION_COMMAND):
            await RosiBot.handle(context.message.text)


async def periodic(seconds: int = 5) -> None:
    """Period Task used to seend weekly reminders

    Args:
        seconds (int, optional): Period in seconds the task is run. Defaults to 5.
    """
    i = 0
    while True:
        logger.debug(f"Running Periodic Task iteration {i}")
        weekday, week, file = get_weekly_lock_file()
        if weekday == MONDAY:
            if os.path.isfile(file):
                logger.debug("Weekly maintenance message already sent. Do nothing")
            else:
                logger.info(
                    "Monday maintenance reminder for this week not sent yet. Create Lock file and send reminder."
                )
                with open(file, "w", encoding="utf-8") as f:
                    f.write("")
                await send(WEEKLY_REMINDER_MESSAGE.format(KW=f"KW {week}"))
        if weekday == FRIDAY:
            if os.path.isfile(file):
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                    if len(content) == 0:
                        logger.info(
                            "Friday maintenance reminder for this week not sent yet. "
                            "Create Lock file and send reminder."
                        )
                        await send(WEEKLY_REMINDER_MESSAGE_FRIDAY)
                        f.write(str(FRIDAY))
            else:
                logger.warning(
                    "Its Friday and not weekly maintenance message is send yet. "
                    "This should not happen. Creating file anyway and send regular maintenance message!"
                )
                Path(file).touch()
                await send(WEEKLY_REMINDER_MESSAGE.format(KW=f"KW {week}"))
        i += 1
        await asyncio.sleep(seconds)


if __name__ == "__main__":
    bot.register(
        BotMention(), contacts=False, groups=[settings.signal_group_id]
    )  # all contacts and groups
    bot._event_loop.create_task(periodic())  # pylint: disable=protected-access
    logger.info("Starting Bot!")
    bot.start()  # type: ignore
