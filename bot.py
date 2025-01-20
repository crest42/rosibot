"""Main Bot implementation
"""
import datetime
import os
import asyncio
from pathlib import Path
import logging

from signalbot import SignalBot, Command, Context

from messages import Messages
from settings import Settings

messages = Messages()
BOT_COMMAND_DELIMITER = "!"

MONDAY = 0
FRIDAY = 5
LOCK_FILE_PATH = "/tmp"
ROSIBOT_PREFIX = "[ROSIBOT]: "
logger = logging.getLogger(__name__
)
logger.setLevel(logging.DEBUG)

def get_weekly_lock_file() -> tuple[int, int, str]:
    """Returns some ad-hoc date information used to handle file based locking

    Returns:
        Tuple[int, int, str]: Tuple of weekday (0-6), week number (0-42) and a filename used for weekly locking
    """
    today = datetime.datetime.today()
    file = f"{LOCK_FILE_PATH}/rosibot_{today.year}_{today.isocalendar().week}"
    return (today.weekday(), today.isocalendar().week, file)

class RosiBot(Command):
    """RosiBot main implementation"""

    def __init__(self, settings: Settings) -> None:
        self.signal_group_id = settings.signal_group_id
        self.signal_bot = SignalBot(
            {"signal_service": settings.signal_service, "phone_number": settings.phone_number}
        )
        self.register()
        self.signal_bot._event_loop.create_task(self.periodic())  # pylint: disable=protected-access


    def register(self) -> None:
        """Wrapper for singalbots register function."""
        self.signal_bot.register(self, contacts=False, groups=[self.signal_group_id])

    def start(self) -> None:
        """Wrapper function to call signalbot's start function. Entrypoint to RosiBot"""
        self.signal_bot.start() # type: ignore

    async def send(self, message: str) -> None:
        """Send a message to group defined in the settings. Prefixes all messages with a BOT identifier"""
        await self.signal_bot.send(self.signal_group_id, ROSIBOT_PREFIX + message)

    async def handle(self, context: Context) -> None:
        """Main handler function for the bot.
        This function checks if a command is a bot command and handles it accordingly.

        Args:
            c (Context): Message context as send by signalbot
        """
        if context.message.text.startswith(BOT_COMMAND_DELIMITER):
            await self._handle(context.message.text)
        else:
            logger.error(f"Invalid bot command {context.message.text}. Do nothing")

    async def _handle(self, text: str) -> None:
        """Bot Command handler. Handles any bot command passed to it.

        Valid Bot commands are supposed to look like: "!<command>"

        Args:
            text (str): Bot command
        """
        logger.debug(f"Received Bot command: {text}")
        if text == "!hilfe":
            message, _ = messages.get_command_message(text)
            if message:
                await self.send(message)
        if text == "!erledigt":
            message, fail = messages.get_command_message(text)
            _, week, file = get_weekly_lock_file()
            with open(file, "a", encoding="utf-8") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size <= 1:
                    logger.debug(
                        f"Weekly maintenance for {week} done. Updating Log file"
                    )
                    f.write("Done")
                    await self.send(message)
                else:
                    logger.debug(
                        f"Weekly maintenance for {week} already done. Do nothing"
                    )
                    if fail:
                        await self.send(fail)

    async def periodic(self, seconds: int = 5) -> None:
        """Period Task used to send weekly reminders

        Args:
            seconds (int, optional): Period in seconds the task is run. Defaults to 5.
        """
        i = 0
        while True:
            logger.debug(f"Running Periodic Task iteration {i}")
            weekday, week, file_name = get_weekly_lock_file()
            if weekday == MONDAY:
                if os.path.isfile(file_name):
                    logger.debug("Weekly maintenance message already sent. Do nothing")
                else:
                    logger.info(
                        "Monday maintenance reminder for this week not sent yet. Create Lock file and send reminder."
                    )
                    with open(file_name, "w", encoding="utf-8") as file:
                        file.write("")
                    message = messages.get_periodic_message("WEEKLY_MONDAY")
                    await self.send(message.format(KW=f"KW {week}"))
            if weekday == FRIDAY:
                if os.path.isfile(file_name):
                    with open(file_name, "r", encoding="utf-8") as file:
                        content = file.read()
                        if len(content) == 0:
                            logger.info(
                                "Friday maintenance reminder for this week not sent yet. "
                                "Create Lock file and send reminder."
                            )
                            message = messages.get_periodic_message("WEEKLY_FRIDAY")
                            await self.send(message)
                            file.write(str(FRIDAY))
                else:
                    logger.warning(
                        "Its Friday and not weekly maintenance message is send yet. "
                        "This should not happen. Creating file anyway and send regular maintenance message!"
                    )
                    Path(file_name).touch()
                    message = messages.get_periodic_message("WEEKLY_MONDAY")
                    await self.send(message.format(KW=f"KW {week}"))
            i += 1
            await asyncio.sleep(seconds)
