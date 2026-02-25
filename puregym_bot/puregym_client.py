import httpx
from bs4 import BeautifulSoup
from pydantic import SecretStr

BASE_URL = "https://www.puregym.dk/"


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

        login_response = self.client.post(
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

    # def get_current_bookings(self):
    #     with httpx.Client(cookies=self.cookies) as client:
    #         r = client.get(f"{BASE_URL}my-bookings")
    #         soup = BeautifulSoup(r.text, "html.parser")
