# %%

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, SecretStr

from puregym_bot.config import config

BASE_URL = "https://www.puregym.dk/"
API_URL = "https://www.puregym.dk/api/"


class Class(BaseModel):
    label: str
    value: int
    type: str


class ClassGroup(BaseModel):
    title: str
    options: list[Class]


class Center(BaseModel):
    label: str
    value: int
    type: str


class CenterGroup(BaseModel):
    label: str
    weight: int
    options: list[Center]


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

    def get_activities(self) -> list[ClassGroup]:
        r = self.client.get(f"{API_URL}get_activities")
        return [ClassGroup.model_validate(c) for c in r.json()["classes"]]

    def get_centers(self) -> list[CenterGroup]:
        r = self.client.get(f"{API_URL}get_activities")
        return [CenterGroup.model_validate(c) for c in r.json()["centers"]]


puregym_client = PureGymClient(config.PUREGYM_USERNAME, config.PUREGYM_PASSWORD)

# %%

puregym_client.get_activities()

# %%
puregym_client.get_centers()
# %%
# curl 'https://www.puregym.dk/api/search_activities?classes%5B%5D=34941&classes%5B%5D=23742&centers%5B%5D=172&centers%5B%5D=123&from=2026-02-25&to=2026-03-18' \
#   -H 'accept: */*' \
#   -H 'accept-language: en-US,en;q=0.9,es;q=0.8' \
#   -H 'cache-control: no-cache' \
#   -b '_vwo_uuid_v2=DD92D982D9858C3469428D222329EE059|e0ec719f001f44f8d64b6f525f191b6a; _vwo_uuid=DD92D982D9858C3469428D222329EE059; _vwo_ds=3%241770846791%3A7.16658917%3A%3A%3A%3A%3A1770846791%3A1770846791%3A1; _vis_opt_s=1%7C; CookieInformationConsent=%7B%22website_uuid%22%3A%2272929c6a-1672-441c-ac8b-4d75e5311a7d%22%2C%22timestamp%22%3A%222026-02-11T21%3A53%3A14.188Z%22%2C%22consent_url%22%3A%22https%3A%2F%2Fwww.puregym.dk%2Ffind-center%2Ffrb-frederiksberg-svoemmehal%22%2C%22consent_website%22%3A%22puregym.dk%22%2C%22consent_domain%22%3A%22www.puregym.dk%22%2C%22user_uid%22%3A%22e4434cea-e002-4bf9-8510-0a6d0afaa749%22%2C%22consents_approved%22%3A%5B%22cookie_cat_necessary%22%5D%2C%22consents_denied%22%3A%5B%22cookie_cat_functional%22%2C%22cookie_cat_statistic%22%2C%22cookie_cat_marketing%22%2C%22cookie_cat_unclassified%22%5D%2C%22user_agent%22%3A%22Mozilla%2F5.0%20%28X11%3B%20Linux%20x86_64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F144.0.0.0%20Safari%2F537.36%22%7D; fw_member=1; SSESSffaa186b839634061b10b542e2b0e0d9=RO74fO3zFgmckzydeNHitp3tJ2TKXoLgtHx-WFCMTCmu7xc-' \
#   -H 'pragma: no-cache' \
#   -H 'priority: u=1, i' \
#   -H 'referer: https://www.puregym.dk/holdtraening' \
#   -H 'sec-ch-ua: "Not(A:Brand";v="8", "Chromium";v="144"' \
#   -H 'sec-ch-ua-mobile: ?0' \
#   -H 'sec-ch-ua-platform: "Linux"' \
#   -H 'sec-fetch-dest: empty' \
#   -H 'sec-fetch-mode: cors' \
#   -H 'sec-fetch-site: same-origin' \
#   -H 'user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
