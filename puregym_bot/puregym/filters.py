from datetime import datetime, time

from puregym_bot.config import TimeSlot
from puregym_bot.puregym.schemas import GymClass


def filter_by_booked(classes: list[GymClass], booked: bool = True) -> list[GymClass]:
    return [c for c in classes if (c.participationId is not None) == booked]


def filter_by_time_slot(classes: list[GymClass], time_slot: TimeSlot) -> list[GymClass]:
    filtered_classes = []
    for c in classes:
        date = datetime.fromisoformat(c.date)
        if date.weekday() != time_slot.day_of_week:
            continue

        class_start = time.fromisoformat(c.startTime)
        class_end = time.fromisoformat(c.endTime)
        if time_slot.start_time <= class_start <= class_end <= time_slot.end_time:
            filtered_classes.append(c)
    return filtered_classes


def filter_by_time_slots(
    classes: list[GymClass], time_slots: list[TimeSlot]
) -> list[GymClass]:

    filtered_classes = []

    for time_slot in time_slots:
        filtered_classes.extend(filter_by_time_slot(classes, time_slot))

    return filtered_classes
