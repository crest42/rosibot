"""Main Bot implementation
"""

from typing import Awaitable, Callable, Any

import datetime
import asyncio
import logging
from enum import IntEnum

import redis
from signalbot import SignalBot, Command, Context

from rosibot.messages import Messages
from rosibot.settings import Settings

messages = Messages()
_settings = Settings()

BOT_COMMAND_DELIMITER = "!"

MONDAY = 0
FRIDAY = 5
LOCK_FILE_PATH = "/tmp"
ROSIBOT_PREFIX = "[ROSIBOT]: "
MAX_COMMAND_LENGTH = 128
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
cache = redis.Redis(host="localhost", port=6379, db=0)


def today() -> tuple[int, int, int]:
    """Returns some ad-hoc date information used to handle cache based locking

    Returns:
        Tuple[int, int]: Tuple of yer, weekday (0-6), week number (0-42)
    """
    _today = datetime.datetime.today()
    return (_today.year, _today.weekday(), _today.isocalendar().week)


def get_cache_key(year: int, week: int) -> str:
    """Returns weekly cache key, used to remember if a periodic message needs to be sent"""
    return f"{year}{week}"


if _settings.debug:
    logger.warning(
        "DEBUG MODE ENABLED. "
        "WILL CLEAR WEEKLY CACHE. "
        "THIS RESULTS IN ALL PERIODIC MESSAGES BEING RESENT. "
        "BE CAREFUL TO AVOID SPAM"
    )
    year_, _, week_ = today()
    cache_key_ = get_cache_key(year_, week_)
    cache.delete(cache_key_)

command_registry: dict[str, Callable[[Any, Any], Awaitable[Any]]] = {}


class PeriodicState(IntEnum):
    """Small state machines used to send periodic messages. Needs some work"""

    NONE = -1
    FRESH = 0
    REMINDER_SENT = 1
    DONE = 2


def register_command(command: str) -> Callable[..., None]:
    """Adds a command and the proper handler function to a global registry"""
    if command in command_registry:
        raise RuntimeError(
            f"Command {command} is already registered at {command_registry[command]}"
        )

    def _register(func: Callable[[Any, Any], Awaitable[Any]]) -> None:
        command_registry[command] = func

    return _register


class RosiBot(Command):
    """RosiBot main implementation"""

    def __init__(self, settings: Settings) -> None:
        self.signal_group_id = settings.signal_group_id
        self.signal_bot = SignalBot(
            {
                "signal_service": settings.signal_service,
                "phone_number": settings.phone_number,
            }
        )
        self.register()
        self.signal_bot._event_loop.create_task(
            self.periodic()
        )  # pylint: disable=protected-access

    async def _handle(self, text: str) -> None:
        """Bot Command handler. Handles any bot command passed to it.

        Valid Bot commands are supposed to look like: "!<command>"

        Args:
            text (str): Bot command
        """
        if text.startswith(BOT_COMMAND_DELIMITER):
            if len(text) > MAX_COMMAND_LENGTH:
                logger.error(
                    f"Invalid Bot command. Length {len(text)} exceeds allowed length of {MAX_COMMAND_LENGTH}"
                )
                return
            await self._handle_command(text.strip())
        else:
            logger.debug(
                "Recieved Messages that does not appear to be a command. Do nothing"
            )

    async def _handle_command(self, command: str) -> None:

        logger.debug(f"Received Bot command: {command}")
        if command in command_registry:
            await command_registry[command](self, command)
        else:
            logger.warning(f"Recieved unknown bot command '{command}'. Ignore")

    def register(self) -> None:
        """Wrapper for singalbots register function."""
        self.signal_bot.register(self, contacts=False, groups=[self.signal_group_id])

    def start(self) -> None:
        """Wrapper function to call signalbot's start function. Entrypoint to RosiBot"""
        self.signal_bot.start()  # type: ignore

    async def send(self, message: str) -> None:
        """Send a message to group defined in the settings. Prefixes all messages with a BOT identifier"""
        await self.signal_bot.send(self.signal_group_id, ROSIBOT_PREFIX + message)

    async def handle(self, context: Context) -> None:
        """Main handler function for the bot.
        This function checks if a command is a bot command and handles it accordingly.

        Args:
            c (Context): Message context as send by signalbot
        """
        await self._handle(context.message.text)

    async def periodic(self, seconds: int = 5) -> None:
        """Period Task used to send weekly reminders

        Args:
            seconds (int, optional): Period in seconds the task is run. Defaults to 5.
        """
        i = 0
        while True:
            logger.debug(f"Running Periodic Task iteration {i}")
            year, weekday, week = today()
            cache_key = get_cache_key(year, week)
            cache_value = cache.get(cache_key)
            if weekday == MONDAY:
                if cache_value is not None:
                    logger.debug("Weekly maintenance message already sent. Do nothing")
                else:
                    logger.info(
                        "Monday maintenance reminder for this week not sent yet. Create Lock file and send reminder."
                    )
                    cache.set(cache_key, PeriodicState.FRESH.value)
                    message = messages.get_periodic_message("WEEKLY_MONDAY")
                    await self.send(message.format(KW=f"KW {week}"))
            if weekday == FRIDAY:
                if cache_value is not None:
                    state = PeriodicState.FRESH.value
                    try:
                        state = int(cache_value.decode("utf-8"))
                    except TypeError:
                        logger.error(
                            "Could not fetch cache content. Error while casting to int"
                        )
                        return
                    if state == PeriodicState.FRESH.value:
                        logger.info(
                            "Friday maintenance reminder for this week not sent yet. "
                            "Create Lock file and send reminder."
                        )
                        message = messages.get_periodic_message("WEEKLY_FRIDAY")
                        await self.send(message)
                        cache.set(cache_key, PeriodicState.REMINDER_SENT.value)
                else:
                    logger.warning(
                        "Its Friday and not weekly maintenance message is send yet. "
                        "This should not happen. Creating file anyway and send regular maintenance message!"
                    )
                    cache.set(cache_key, PeriodicState.REMINDER_SENT.value)
                    message = messages.get_periodic_message("WEEKLY_MONDAY")
                    await self.send(message.format(KW=f"KW {week}"))
            i += 1
            await asyncio.sleep(seconds)

    @register_command("!hilfe")
    async def _handle_help(self, command: str) -> None:
        message, _ = messages.get_command_message(command)
        if message:
            await self.send(message)

    @register_command("!erledigt")
    async def _handle_maintenance_done(self, command: str) -> None:
        message, fail = messages.get_command_message(command)
        year, _, week = today()
        cache_key = get_cache_key(year, week)
        cache_value = cache.get(cache_key)
        state = PeriodicState.FRESH.value
        if cache_value is not None:
            try:
                state = int(cache_value.decode("utf-8"))
            except TypeError:
                logger.error(
                    "Could not fetch cache content. Error while casting to int"
                )
                return
        if state != PeriodicState.DONE:
            logger.debug(f"Weekly maintenance for {week} done. Updating Log file")
            cache.set(cache_key, PeriodicState.DONE.value)
            await self.send(message)
        else:
            logger.debug(f"Weekly maintenance for {week} already done. Do nothing")
            if fail:
                await self.send(fail)
