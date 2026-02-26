from dataclasses import dataclass
from typing import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

from puregym_bot.bot import handlers
from puregym_bot.bot.dependencies import HandlerContext


@dataclass(frozen=True)
class CommandSpec:
    name: str
    description: str
    handler: Callable[[Update, ContextTypes.DEFAULT_TYPE, HandlerContext], Awaitable[None]]
    allow_inactive: bool = False


COMMANDS: list[CommandSpec] = [
    CommandSpec("start", "Start the bot", handlers.start, allow_inactive=True),
    CommandSpec("stop", "Stop the bot", handlers.stop, allow_inactive=True),
    CommandSpec("booked_classes", "Show your upcoming bookings", handlers.booked_classes),
    CommandSpec("class_ids", "List available class types", handlers.all_class_ids),
    CommandSpec("center_ids", "List available centers", handlers.all_center_ids),
    CommandSpec("test_inline", "Test inline buttons", handlers.test_inline),
]
