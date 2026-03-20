from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from puregym_bot.bot.callback_data import BookingCallback, BookingCallbackAction, ChoicePickCallback
from puregym_bot.formatting import format_telegram_class_summary


@dataclass(frozen=True)
class ButtonSpec:
    label: str
    callback_data: str


@dataclass(frozen=True)
class MessageSpec:
    text: str
    buttons: tuple[tuple[ButtonSpec, ...], ...] = ()


def message_markup(message: MessageSpec) -> InlineKeyboardMarkup | None:
    if not message.buttons:
        return None
    keyboard = []
    for row in message.buttons:
        keyboard.append(
            [InlineKeyboardButton(button.label, callback_data=button.callback_data) for button in row]
        )
    return InlineKeyboardMarkup(keyboard)


def build_keep_booking_prompt(participation_id: str, text: str) -> MessageSpec:
    return MessageSpec(
        text=text,
        buttons=(
            (
                ButtonSpec(
                    label="Accept",
                    callback_data=BookingCallback(
                        action=BookingCallbackAction.ACCEPT,
                        participation_id=participation_id,
                    ).to_callback_data(),
                ),
                ButtonSpec(
                    label="Reject",
                    callback_data=BookingCallback(
                        action=BookingCallbackAction.REJECT,
                        participation_id=participation_id,
                    ).to_callback_data(),
                ),
            ),
        ),
    )


def build_cancel_booking_prompt(participation_id: str, text: str) -> MessageSpec:
    return MessageSpec(
        text=text,
        buttons=(
            (
                ButtonSpec(
                    label="Cancel",
                    callback_data=BookingCallback(
                        action=BookingCallbackAction.CANCEL,
                        participation_id=participation_id,
                    ).to_callback_data(),
                ),
            ),
        ),
    )


def build_confirmed_reminder_prompt(participation_id: str) -> MessageSpec:
    prompt = build_cancel_booking_prompt(
        participation_id,
        text="Reminder: your class is coming up soon. If you changed your mind, cancel now.",
    )
    return MessageSpec(
        text=prompt.text,
        buttons=((ButtonSpec(label="Cancel now", callback_data=prompt.buttons[0][0].callback_data),),),
    )


def build_selected_choice_confirmation_prompt(
    title: str,
    class_date: str,
    start_time: str,
    location: str,
    participation_id: str,
) -> MessageSpec:
    return build_keep_booking_prompt(
        participation_id,
        text=(
            f"Booked: {format_telegram_class_summary(class_date, start_time, title, location)}\n"
            "Do you want to keep it?"
        ),
    )


def build_choice_pick_button(choice_id: int, option_index: int, label: str) -> ButtonSpec:
    return ButtonSpec(
        label=label,
        callback_data=ChoicePickCallback(
            choice_id=choice_id,
            option_index=option_index,
        ).to_callback_data(),
    )
