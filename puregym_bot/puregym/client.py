import asyncio
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
        self.username = username
        self.password = password
        self.client = httpx.AsyncClient(follow_redirects=True)
        self._login_lock = asyncio.Lock()

    async def login(self) -> None:
        r = await self.client.get(BASE_URL)
        soup = BeautifulSoup(r.text, "html.parser")

        form_build_id_input = soup.find("input", {"name": "form_build_id"})

        if form_build_id_input is None:
            raise ValueError("Could not find form_build_id in the login page")

        form_build_id = form_build_id_input.get("value")

        await self.client.post(
            BASE_URL,
            data={
                "form_build_id": form_build_id,
                "form_id": "user_login_form",
                "name": self.username,
                "pass": self.password.get_secret_value(),
                "redirect_url": "",
                "op": "Log ind",
            },
            timeout=10,
        )

    async def _request_json(self, method: str, url: str, **kwargs):
        r = await self.client.request(method, url, **kwargs)
        if r.status_code in (401, 403) or "user_login_form" in r.text:
            async with self._login_lock:
                await self.login()
            r = await self.client.request(method, url, **kwargs)
        r.raise_for_status()
        return r.json()

    async def get_all_class_types(self) -> list[GymClassTypesGroup]:
        data = await self._request_json("GET", f"{API_URL}get_activities")
        return [GymClassTypesGroup.model_validate(c) for c in data["classes"]]

    async def get_all_centers(self) -> list[CenterGroup]:
        data = await self._request_json("GET", f"{API_URL}get_activities")
        return [CenterGroup.model_validate(c) for c in data["centers"]]

    async def get_available_classes(
        self,
        class_ids: list[int],
        center_ids: list[int],
        from_date: str = datetime.today().strftime("%Y-%m-%d"),
        to_date: str = (
            datetime.today() + timedelta(days=config.MAX_DAYS_IN_ADVANCE)
        ).strftime("%Y-%m-%d"),
    ) -> list[GymClass]:
        data = await self._request_json(
            "GET",
            f"{API_URL}search_activities",
            params={
                "classes[]": class_ids,
                "centers[]": center_ids,
                "from": from_date,
                "to": to_date,
            },
        )

        return [
            GymClass.model_validate({**item, "date": day["date"]})
            for day in data
            for item in day["items"]
        ]

    async def book_class(self, gym_class: GymClass):
        return await self._request_json(
            "POST",
            f"{API_URL}book_activity",
            data={
                "bookingId": gym_class.bookingId,
                "activityId": gym_class.activityId,
                "payment_type": gym_class.payment_type,
            },
        )

    async def unbook_class(self, gym_class: GymClass):
        return await self._request_json(
            "POST",
            f"{API_URL}unbook_activity",
            data={
                "participationId": gym_class.participationId,
            },
        )

    async def aclose(self) -> None:
        await self.client.aclose()
