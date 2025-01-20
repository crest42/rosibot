"""Wrapper class to hold messages for certain command or periodic messages"""

from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)
MESSAGES_FILE = "messages.json"

class Messages:
    """Wrapper Class for message definitions.

    Messages can be either of periodic type or of a command type.
    Commands are usually user input that prompt the bot to do something.
    Periodic Messages are simple messages send on a periodic basis.

    """
    class CommandMessage:
        """A message sent as a response to a command.
        Commands always have a success message attached. 
        Optionally commands can also contain a failure message that can be returned on errors
        """

        def __init__(
            self, command: str, success: str, fail: Optional[str] = None
        ) -> None:
            self.command = command
            self.success = success
            self.fail = fail

    class PeriodicMessage:
        """A periodic message. Periodic messages only consists of a single message with no failure message"""

        def __init__(self, message: str) -> None:
            self.message = message

    def __init__(self, message_file: str = MESSAGES_FILE):
        self.message_file = message_file
        self.periodic: dict[str, Messages.PeriodicMessage] = {}
        self.commands: dict[str, Messages.CommandMessage] = {}
        with open(self.message_file, "r", encoding="utf-8") as f:
            json_messages = json.load(f)
            if not isinstance(json_messages, dict) or len(json_messages) == 0:
                logger.warning(
                    f"No messages could be retrieved from {self.message_file}"
                )
                return
            if "periodic" in json_messages:
                for message_id, message in json_messages["periodic"].items():
                    if isinstance(message_id, str) and isinstance(message, str):
                        self.periodic[message_id] = Messages.PeriodicMessage(message)
            if "commands" in json_messages:
                for command, message in json_messages["commands"].items():
                    if isinstance(message, str):
                        self.commands[command] = Messages.CommandMessage(
                            command, message
                        )
                    elif isinstance(message, dict) and len(message) == 2:
                        self.commands[command] = Messages.CommandMessage(
                            command, message["SUCCESS"], message["FAIL"]
                        )
                    else:
                        raise RuntimeError(
                            f"Could not parse message dict for command {command}"
                        )

    def get_periodic_message(self, message_id: str) -> str:
        """Returns success and failure messages for a given periodic message

        Args:
            message_id (str): The message ID of the periodic message we want to fetch

        Raises:
            RuntimeError: Raised if no periodic message for this id exists

        Returns:
            str: The message we asked for
        """
        if message_id in self.periodic:
            return self.periodic[message_id].message
        raise RuntimeError(f"No periodic message with index: {message_id}")

    def get_command_message(self, command: str) -> tuple[str, Optional[str]]:
        """Returns success and failure messages for a given command.

        Args:
            command (str): String Command we want the messages for.
            Commands can be any string but usually follow: !<command>

        Raises:
            RuntimeError: Raised if the queried command does not exist

        Returns:
            Tuple[str, Optional[str]]: Return a success message and an optional failure message
        """
        if command in self.commands:
            return (self.commands[command].success, self.commands[command].fail)
        raise RuntimeError(f"Could not find messages for command {command}")
