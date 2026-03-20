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
    CommandSpec("start", "Enable automatic booking", handlers.start, allow_inactive=True),
    CommandSpec("stop", "Disable automatic booking", handlers.stop, allow_inactive=True),
    CommandSpec("status", "Show automatic booking status", handlers.status, allow_inactive=True),
    CommandSpec("booked", "Show your upcoming bookings", handlers.booked_classes, allow_inactive=True),
    CommandSpec("class_ids", "List available class types", handlers.all_class_ids, allow_inactive=True),
    CommandSpec("center_ids", "List available centers", handlers.all_center_ids, allow_inactive=True),
    CommandSpec("run_now", "Run booking cycle immediately", handlers.run_now),
]
