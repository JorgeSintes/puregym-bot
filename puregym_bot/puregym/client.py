from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup
from pydantic import SecretStr

from puregym_bot.config import config
from puregym_bot.puregym.schemas import CenterGroup, GymClass, GymClassTypesGroup

BASE_URL = "https://www.puregym.dk/"
API_URL = "https://www.puregym.dk/api/"


class PureGymClient:
    def __init__(self, username: str, password: SecretStr):
        self.client = httpx.Client(follow_redirects=True)
        self.login(username, password)

    def login(self, username: str, password: SecretStr):
        r = self.client.get(BASE_URL)
        soup = BeautifulSoup(r.text, "html.parser")

        form_build_id_input = soup.find("input", {"name": "form_build_id"})

        if form_build_id_input is None:
            raise ValueError("Could not find form_build_id in the login page")

        form_build_id = form_build_id_input.get("value")

        self.client.post(
            BASE_URL,
            data={
                "form_build_id": form_build_id,
                "form_id": "user_login_form",
                "name": username,
                "pass": password.get_secret_value(),
                "redirect_url": "",
                "op": "Log ind",
            },
            timeout=10,
        )

    def get_all_class_types(self) -> list[GymClassTypesGroup]:
        r = self.client.get(f"{API_URL}get_activities")
        return [GymClassTypesGroup.model_validate(c) for c in r.json()["classes"]]

    def get_all_centers(self) -> list[CenterGroup]:
        r = self.client.get(f"{API_URL}get_activities")
        return [CenterGroup.model_validate(c) for c in r.json()["centers"]]

    def find_class_types_ids(self, class_names: list[str]) -> list[int]:
        activities = self.get_all_class_types()
        class_ids = []
        for group in activities:
            for option in group.options:
                if option.label in class_names:
                    class_ids.append(option.value)

        if len(class_ids) != len(class_names):
            raise ValueError(
                f"Could not find all class ids for class names: {class_names}"
            )
        return class_ids

    def find_centers_ids(self, center_names: list[str]) -> list[int]:
        centers = self.get_all_centers()
        center_ids = []
        for group in centers:
            for option in group.options:
                if option.label in center_names:
                    center_ids.append(option.value)

        if len(center_ids) != len(center_names):
            raise ValueError(
                f"Could not find all center ids for center names: {center_names}"
            )
        return center_ids

    def get_available_classes(self) -> list[GymClass]:
        class_ids = self.find_class_types_ids(config.INTERESTED_CLASSES)
        center_ids = self.find_centers_ids(config.INTERESTED_CENTERS)

        r = self.client.get(
            f"{API_URL}search_activities",
            params={
                "classes[]": class_ids,
                "centers[]": center_ids,
                "from": datetime.today().strftime("%Y-%m-%d"),
                "to": (
                    datetime.today() + timedelta(days=config.MAX_DAYS_IN_ADVANCE)
                ).strftime("%Y-%m-%d"),
            },
        )

        return [
            GymClass.model_validate({**item, "date": day["date"]})
            for day in r.json()
            for item in day["items"]
        ]

    def get_booked_classes(self) -> list[GymClass]:
        classes = self.get_available_classes()

        return [c for c in classes if c.participationId is not None]

    def book_class(self, gym_class: GymClass):
        r = self.client.post(
            f"{API_URL}book_activity",
            data={
                "bookingId": gym_class.bookingId,
                "activityId": gym_class.activityId,
                "payment_type": gym_class.payment_type,
            },
        )
        return r.json()

    def unbook_class(self, gym_class: GymClass):
        r = self.client.post(
            f"{API_URL}unbook_activity",
            data={
                "participationId": gym_class.participationId,
            },
        )
        return r.json()
