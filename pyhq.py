import json
import requests
import re
import datetime
import os
import time
from typing import Union

_first_re = re.compile("(.)([A-Z][a-z]+)")
_cap_re = re.compile("([a-z0-9])([A-Z])")
def _to_snake(name):
    s1 = _first_re.sub(r"\1_\2", name)
    return _cap_re.sub(r"\1_\2", s1).lower()


class HQUserLeaderboard:
    def __init__(self, **kwargs):
        self.total_cents = kwargs.get("total_cents")
        self.total = kwargs.get("total")
        self.unclaimed = kwargs.get("unclaimed")
        for p in ("alltime", "weekly"):
            for v in ("wins", "total", "rank"):
                try:
                    setattr(self, f"{p}_{v}", kwargs.get(p).get(v))
                except:
                    pass


class HQUserInfo:
    def __init__(self, **kwargs):
        self.user_id = kwargs.get("user_id")
        self.username = kwargs.get("username")
        self.avatar_url = kwargs.get("avatar_url")
        self.created_timestamp = kwargs.get("created_timestamp")
        self.broadcasts = kwargs.get("broadcasts")  # unused
        self.featured = kwargs.get("featured")  # unused
        self.referral_url = kwargs.get("referral_url")  # property?
        self.high_score = kwargs.get("high_score")
        self.games_played = kwargs.get("games_played")
        self.win_count = kwargs.get("win_count") # different than leaderboard.alltime_wins cuz i dont know, i think this is the accurate one
        self.blocked = kwargs.get("blocked")
        self.blocks_me = kwargs.get("blocks_me")
        self.achievement_count = kwargs.get("achievement_count") # int
        try:
            x = kwargs.get("leaderboard")
            if isinstance(x, dict):
                kwargs2 = {}
                for k, v in x.items():
                    kwargs2[_to_snake(k)] = v
                self.leaderboard = HQUserLeaderboard(**kwargs2)
            elif isinstance(x, HQUserLeaderboard):
                self.leaderboard = x
        except Exception as e:
            raise e


class HQMeInfo(HQUserInfo):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.friend_ids = kwargs.get("friend_ids")
        self.stk = kwargs.get("stk")  # unused?
        self.voip = kwargs.get("voip")
        self.device_tokens = kwargs.get("device_tokens")
        self.preferences = kwargs.get("preferences")
        self.lives = kwargs.get("lives")
        self.phone_number = kwargs.get("phone_number")
        self.referred = kwargs.get("referred")
        self.streak_info = kwargs.get("streak_info") # no class until purpose is clear

class HQBalanceInfo:
    def __init__(self, **kwargs):
        self.prize_total = kwargs.get("prize_total") # "$123.45"
        self.paid = kwargs.get("paid") # "$123.45"
        self.pending = kwargs.get("pending") # "$123.45"
        self.unpaid = kwargs.get("unpaid") # same thing, current balance
        self.eligible_for_payout = kwargs.get("eligible_for_payout") # bool
        self.has_pending = kwargs.get("has_pending") # bool
        self.payouts_connected = kwargs.get("payouts_connected") # bool
        self.payouts_email = kwargs.get("payouts_email") # first used email
        self.document_required = kwargs.get("document_required") # bool
        self.document_status = kwargs.get("document_status") # str


class HQPayout:
    def __init__(self, **kwargs):
        self.payout_id = kwargs.get("payout_id") # int
        self.user_id = kwargs.get("user_id") # int
        self.amount = kwargs.get("amount") # "$123.45"
        self.currency = kwargs.get("currency") # "USD"
        self.target_user_id = kwargs.get("target_user_id") # ?
        self.target_email = kwargs.get("target_email") # email to withdraw
        self.target_phone = kwargs.get("target_phone") # ?
        self.status = kwargs.get("status") # 10001 if succeeded?
        _md = kwargs.get("metadata")
        self.metadata = {
            "payouts_connected": _md.get("payoutsConnected"),
            "client": _md.get("client"),
            "sender_batch_id": _md.get("senderBatchId"),
            "batchId": _md.get("batchId")
        }
        self.created = kwargs.get("created") # button hit, YYYY-MM-DDTHH:MM:SS.000Z
        self.modified = kwargs.get("modified") # successful, same format


class HQPayoutInfo:
    def __init__(self, **kwargs):
        self.balance = HQBalanceInfo(**(kwargs.get("balance")))
        self.payouts = []

        for payout in kwargs.get("payouts", []):
            self.payouts.append(HQPayout(**payout))


class HQClient:
    def __init__(self, login_token: str, client: str="Android/1.6.2", user_agent: str="okhttp/3.8.0", caching=False, cache_time=15, no_ws_requests=False):
        self.login_token = login_token
        self.headers = {
            "x-hq-client": client,
            "user-agent": user_agent
        }
        self.auth_token = self.get_auth_token()
        self.ws = None
        self.ws_on_message = lambda x: None
        self.ws_on_error = lambda x: None
        self.ws_on_close = lambda x: None
        self.caching = caching  # probably could just decorate but im too lazy
        self.cache_time = cache_time
        self._cache = {}
        self.no_ws_requests = no_ws_requests

    @property
    def default_headers(self) -> dict:
        return {
            "x-hq-client": self.headers["x-hq-client"],
            "authorization": "Bearer " + self.auth_token,
            "user-agent": self.headers["user-agent"]
        }

    def get_auth_token(self) -> str:
        return requests.post("https://api-quiz.hype.space/tokens/", headers=self.headers, data={'token': self.login_token}).json()['authToken']

    def valid_auth(self) -> bool:
        return "active" in self.schedule()

    def make_it_rain(self) -> bool:
        return requests.post("https://api-quiz.hype.space/easter-eggs/makeItRain", headers=self.default_headers).status_code == 200

    def search_users(self, user: str) -> list:
        if self.caching:
            if "search_users" in self._cache:
                if user in self._cache["search_users"]:
                    if (time.time() - self._cache["search_users"][user]["last_update"]) < self.cache_time:
                        return self._cache["search_users"][user]["value"]
        response = requests.get("https://api-quiz.hype.space/users?q=" + user, headers=self.default_headers)
        ret = []
        for x in response.json()["data"]:
            kwargs = {}
            for k, v in x.items():
                kwargs[_to_snake(k)] = v
            ret.append(HQUserInfo(**kwargs))
        if self.caching:
            if "search_users" not in self._cache:
                self._cache["search_users"] = {}
            self._cache["search_users"][user] = {
                "value": ret,
                "last_update": time.time()
            }
        return ret

    def user_info(self, something) -> HQUserInfo:
        if isinstance(something, str):
            search = self.search_users(something)
            if not search:
                raise Exception("User not found")
            else:
                user_id = search[0].user_id
        elif isinstance(something, int):
            user_id = something
        if self.caching:
            if "user_info" in self._cache:
                if user_id in self._cache["user_info"]:
                    if (time.time() - self._cache["user_info"][user_id]["last_update"]) < self.cache_time:
                        return self._cache["user_info"][user_id]["value"]
        response = requests.get("https://api-quiz.hype.space/users/me", headers=self.default_headers)
        kwargs = {}
        for k, v in response.json().items():
            kwargs[_to_snake(k)] = v
        ret = HQUserInfo(**kwargs)
        if self.caching:
            if "user_info" not in self._cache:
                self._cache["user_info"] = {}
            self._cache["user_info"][user_id] = {
                "value": ret,
                "last_update": time.time()
            }
        return ret

    def me(self) -> HQMeInfo:
        response = requests.get("https://api-quiz.hype.space/users/me", headers=self.default_headers)
        kwargs = {}
        for k, v in response.json().items():
            kwargs[_to_snake(k)] = v
        return HQMeInfo(**kwargs)

    # i actually dont know if this works so please forgive me if it doesnt lol
    def cashout(self, paypal: str) -> Union[HQPayout, dict]:
        response = requests.post("https://api-quiz.hype.space/users/me/payouts", headers=self.default_headers, data={"email": paypal}).json()
        if "errorCode" in response:
            return response
        else:
            kwargs = {}
            for k, v in response["data"].items():
                kwargs[_to_snake(k)] = v
            return HQPayout(**kwargs)

    def add_referral(self, referral: str) -> bool:
        return requests.patch("https://api-quiz.hype.space/users/me", headers=self.default_headers, data={"referringUsername": referral}).status_code == 200

    def schedule(self) -> dict:
        if self.caching:
            if "schedule" in self._cache:
                if (time.time() - self._cache["schedule"]["last_update"]) < self.cache_time:
                    return self._cache["schedule"]["value"]
        ret = requests.get("https://api-quiz.hype.space/shows/now?type=hq", headers=self.default_headers).json()
        if self.caching:
            if "schedule" not in self._cache:
                self._cache["schedule"] = {}
            self._cache["schedule"] = {
                "value": ret,
                "last_update": time.time()
            }
        return ret

    def aws_credentials(self) -> dict:
        return requests.get("https://api-quiz.hype.space/credentials/s3", headers=self.default_headers).json()

    def delete_avatar(self) -> str:
        return requests.delete("https://api-quiz.hype.space/users/me/avatarUrl", headers=self.default_headers).json()["avatarUrl"]

    def add_friend(self, something) -> dict:
        if isinstance(something, int):
            user_id = int(something)
        elif isinstance(something, str):
            search = self.search_users(something)
            if not search:
                raise Exception("user not found")
            user_id = search[0].user_id
        elif isinstance(something, HQUserInfo):
            user_id = something.user_id
        response = requests.post(f"https://api-quiz.hype.space/friends/{user_id}/requests", headers=self.default_headers).json()
        return {
            "requested_user": self.user_info(response["requestedUser"]["userId"]),
            "requesting_user": self.user_info(response["requestingUser"]["userId"]),
            "status": response["status"]
        }

    def friend_status(self, something):
        if isinstance(something, int):
            user_id = int(something)
        elif isinstance(something, str):
            search = self.search_users(something)
            if not search:
                raise Exception("user not found")
            user_id = search[0].user_id
        return requests.get(f"https://api-quiz.hype.space/friends/{user_id}/status", headers=self.default_headers).json()["status"]

    def accept_friend(self, something) -> dict:
        if isinstance(something, int):
            user_id = int(something)
        elif isinstance(something, str):
            search = self.search_users(something)
            if not search:
                raise Exception("user not found")
            user_id = search[0].user_id
        response = requests.put(f"https://api-quiz.hype.space/friends/{user_id}/status", headers=self.default_headers, data={
                "status": "ACCEPTED"
            }).json()
        return {
            "requested_user": self.user_info(response["requestedUser"]["userId"]),
            "requesting_user": self.user_info(response["requestingUser"]["userId"]),
            "status": response["status"],
            "accepted_timestamp": response["created"]  # milliseconds(?)
        }

    def remove_friend(self, something) -> bool:
        if isinstance(something, int):
            user_id = int(something)
        elif isinstance(something, str):
            search = self.search_users(something)
            if not search:
                raise Exception("user not found")
            user_id = search[0].user_id
        return requests.delete(f"https://api-quiz.hype.space/friends/{user_id}", headers=self.default_headers).json()["result"]

    def payouts(self) -> HQPayoutInfo:
        response = requests.get("https://api-quiz.hype.space/users/me/payouts", headers=self.default_headers).json()
        kwargs = {}
        for k, v in response.items():
            kwargs[_to_snake(k)] = v
        for k, v in response["balance"].copy().items():
            kwargs["balance"][_to_snake(k)] = v
        for i, x in enumerate(kwargs["payouts"]):
            d = {}
            for k, v in x.items():
                d[_to_snake(k)] = v
            kwargs["payouts"][i] = d
        return HQPayoutInfo(**kwargs)

    def socket_url(self) -> str:
        if self.no_ws_requests:
            return "ws://127.0.0.1:6789"  # tbh just replace the line its one method no args
        x = self.schedule()
        if x["active"]:
            return x["broadcast"]["socketUrl"].replace("https", "wss")

    def generate_subscribe(self) -> str:
        if not self.no_ws_requests:
            x = self.schedule()
            broadcast_id = x["broadcast"]["broadcastId"]
        else:
            broadcast_id = "placeholder_broadcastid"
        return json.dumps({
            "type": "subscribe",
            "broadcastId": broadcast_id
        })

    def generate_answer(self, question_id: int, answer_id: int) -> str:
        if not self.no_ws_requests:
            x = self.schedule()
            broadcast_id = x["broadcast"]["broadcastId"]
        else:
            broadcast_id = "placeholder_broadcastid"

        return json.dumps({
            "type": "answer",
            "questionId": question_id,
            "broadcastId": broadcast_id,
            "answerId": answer_id
        })

    def generate_extra_life(self, question_id: int) -> str:
        if not self.no_ws_requests:
            x = self.schedule()
            broadcast_id = x["broadcast"]["broadcastId"]
        else:
            broadcast_id = "placeholder_broadcastid"

        return json.dumps({
            "type": "useExtraLife",
            "broadcastId": broadcast_id,
            "questionId": question_id
        })


def verify(phone: str, headers: dict={}) -> str:
    try:
        return requests.post("https://api-quiz.hype.space/verifications", headers={
            "x-hq-client": headers.get("x-hq-client") or "iOS/1.3.12 b96"
        }, data={
            "method": "sms",
            "phone": phone
        }).json()["verificationId"]
    except KeyError:
        raise Exception("invalid phone number")


def submit_code(verification_id: str, code: str) -> dict:
    return requests.post("https://api-quiz.hype.space/verifications/" + verification_id, data={"code": code}).json()


def username_available(username: str) -> bool:
    return not bool(requests.post("https://api-quiz.hype.space/usernames/available", data={"username": username}).json())


def create_user(username: str, verification_id: str, referral: str="", region: str="US", language: str="en"):
    return requests.post("https://api-quiz.hype.space/users", data={
        "country": region,
        "language": language,
        "referringUsername": referral,
        "username": username,
        "verificationId": verification_id
    }).json()
