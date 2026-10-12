"""Geely EM platform API client.

Both signature schemes were verified byte-exact against traffic captured from
the official Geely Global app (com.geely.global 1.1.1, EU build).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from email.utils import formatdate
from urllib.parse import parse_qsl, quote, urlsplit

import requests
from cryptography.hazmat.primitives import padding as cpad
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as apad
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import (
    APP_ACCESS_KEY,
    APP_AUTH,
    APP_GATEWAY,
    APP_SECRET,
    APP_VERSION,
    CLIENT_ID,
    MSG_APP_ID,
    RSA_PUB,
    SNC_APP_ID,
    SNC_PROJECT_ID,
    SNC_SECRET,
    SNC_WHITELIST,
    TMP_TENANT,
    TSP_GATEWAY,
    USER_CENTER,
    XVIN_IV,
    XVIN_KEY,
)

_LOGGER = logging.getLogger(__name__)


def rsa_encrypt(plain: str) -> str:
    key = serialization.load_der_public_key(base64.b64decode(RSA_PUB))
    return base64.encodebytes(key.encrypt(plain.encode(), apad.PKCS1v15())).decode().strip()


def gmt_now() -> str:
    return formatdate(usegmt=True).replace("+0000 GMT", " GMT")


def xvin(vin: str) -> str:
    p = cpad.PKCS7(128).padder()
    data = p.update(vin.encode()) + p.finalize()
    e = Cipher(algorithms.AES(XVIN_KEY), modes.CBC(XVIN_IV)).encryptor()
    return base64.b64encode(e.update(data) + e.finalize()).decode()


class GeelyAuthError(Exception):
    """Raised when the session is rejected and a re-login is needed."""


class GeelyApiError(Exception):
    """Raised on other API failures."""


class GeelyEuClient:
    def __init__(self, email: str, password: str, country: str = "DE", language: str = "de"):
        self.email = email
        self.password = password
        self.country = country
        self.language = language
        self.device_id = uuid.uuid4()
        self.user_center_token: str | None = None
        self.user_id: str | None = None
        self.access_token: str | None = None
        self.access_token_exp: int = 0
        self.vins: list[str] = []
        self.vehicles: list[dict] = []
        self.session = requests.Session()

    # ---------------- app platform (X-HMAC) ----------------
    def _app_headers(self, method: str, path: str, qs: str, body: str) -> dict:
        date = gmt_now()
        h = {
            "Client-Id": CLIENT_ID,
            "User-Agent": (
                f"Device/Xiaomi AppName/Geely AppVersion/{APP_VERSION} "
                "Platform/android OSVersion/14 Ditto/true"
            ),
            "Call-Source": "android",
            "Device-Type": "app",
            "Device-Name": "M2102J20SG",
            "Language": f"{self.language}-US",
            "X-Language": f"{self.language}-US",
            "appCode": "eu-app",
            "app-authorization": APP_AUTH,
            "msgClientId": APP_AUTH,
            "msgAppId": MSG_APP_ID,
            "Accept-Language": f"{self.language}-US",
            "Country": self.country,
            "AppVersion": APP_VERSION,
            "App-Code": CLIENT_ID,
            "RegistCountry": self.country,
            "Tmp-Tenant-Code": TMP_TENANT,
            "Brand": "GEELY",
            "appId": "TSP",
            "appSecret": "zeekr_tis",
            "X-DATE": date,
            "X-HMAC-ALGORITHM": "hmac-sha256",
            "X-HMAC-ACCESS-KEY": APP_ACCESS_KEY,
            "X-HMAC-SIGNATURE": base64.b64encode(
                hmac.new(
                    APP_SECRET.encode(),
                    f"{method}\n/{path}\n{qs}\n{APP_ACCESS_KEY}\n{date}\n".encode(),
                    hashlib.sha256,
                ).digest()
            ).decode(),
        }
        if body:
            h["X-HMAC-DIGEST"] = base64.b64encode(
                hmac.new(APP_SECRET.encode(), body.encode(), hashlib.sha256).digest()
            ).decode()
            h["Content-Type"] = "application/json; charset=utf-8"
        if self.user_center_token:
            h["Authorization"] = self.user_center_token
        return h

    def _app_request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        qs = ""
        if params:
            qs = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in sorted(params.items()))
        body = json.dumps(json_body) if json_body is not None else ""
        h = self._app_headers(method, path, qs, body)
        url = APP_GATEWAY + path + (f"?{qs}" if qs else "")
        r = self.session.request(
            method, url, data=body.encode() if body else None, headers=h, timeout=30
        )
        try:
            return r.json()
        except ValueError as exc:
            raise GeelyApiError(f"non-JSON response from {path}: HTTP {r.status_code}") from exc

    # ---------------- TSP platform (x-signature) ----------------
    def _tsp_headers(self, method: str, url: str, body: bytes, extra: dict | None = None) -> dict:
        p = urlsplit(url)
        nonce = str(uuid.uuid4())
        ts = str(int(time.time() * 1000))
        hdrs = {
            "X-APP-OS-VERSION": "",
            "X-APP-ID": SNC_APP_ID,
            "X-PROJECT-ID": SNC_PROJECT_ID,
            "Content-Type": "application/json; charset=UTF-8",
            "AppId": "ONEX97FB91F061405",
            "X-API-SIGNATURE-VERSION": "2.0",
            "X-P": "Android",
            "ACCEPT-LANGUAGE": f"{self.language}-DE",
            "X-API-SIGNATURE-NONCE": nonce,
            "X-TIMESTAMP": ts,
            "X-DEVICE-ID": str(self.device_id),
            "X-PLATFORM": "APP",
        }
        if self.access_token:
            hdrs["Authorization"] = self.access_token
        if extra:
            hdrs.update(extra)
        canon = ""
        for k in sorted(hdrs):
            lk = k.lower()
            if lk not in SNC_WHITELIST:
                continue
            v = hdrs[k]
            if lk in ("x-vin", "authorization") and not v:
                continue
            canon += f"{lk}:{v}\n"
        if p.query:
            kvs = sorted(f"{k}={v}" for k, v in parse_qsl(p.query, keep_blank_values=True))
            canon += "&".join(kvs) + "\n"
        if body:
            canon_body = json.dumps(json.loads(body), separators=(",", ":"), ensure_ascii=False)
            canon += base64.b64encode(hashlib.md5(canon_body.encode()).digest()).decode() + "\n"
        canon += method.upper() + "\n" + p.path
        hdrs["x-signature"] = base64.b64encode(
            hmac.new(SNC_SECRET.encode(), canon.encode(), hashlib.sha256).digest()
        ).decode()
        return hdrs

    def _tsp_request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        extra_headers: dict | None = None,
        auth: bool = True,
    ) -> dict:
        body = b""
        if json_body is not None:
            body = json.dumps(json_body, separators=(",", ":")).encode()
        qs = ""
        if params:
            qs = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in sorted(params.items()))
        url = TSP_GATEWAY + path + (f"?{qs}" if qs else "")
        headers = self._tsp_headers(method, url, body, extra=extra_headers)
        if not auth and "Authorization" in headers:
            del headers["Authorization"]
        r = self.session.request(
            method, url, data=body if body else None, headers=headers, timeout=30
        )
        try:
            data = r.json()
        except ValueError as exc:
            raise GeelyApiError(f"non-JSON response from {path}: HTTP {r.status_code}") from exc
        code = str(data.get("code", ""))
        if code == "079021":
            raise GeelyAuthError(f"{path}: session expired")
        return data

    # ---------------- flow ----------------
    def login(self) -> None:
        r = self._app_request(
            "POST",
            f"{USER_CENTER}/auth/loginByEmailEncrypt",
            json_body={
                "email": self.email,
                "codeId": "",
                "code": "",
                "password": rsa_encrypt(self.password),
            },
        )
        if not r.get("success"):
            raise GeelyAuthError(f"login failed: {r.get('code')} {r.get('msg')}")
        self.user_center_token = r["data"]["tokenValue"]

        r = self._app_request("POST", f"{USER_CENTER}/user/info")
        self.user_id = (r.get("data") or {}).get("uuid")

        r = self._app_request(
            "GET",
            f"{USER_CENTER}/user/tspCode",
            params={"tspClientId": CLIENT_ID},
        )
        code = (r.get("data") or {}).get("code")
        if not code:
            raise GeelyAuthError(f"tspCode failed: {r}")

        r = self._tsp_request(
            "POST",
            "/ms-user-auth/v1.0/auth/login",
            json_body={
                "identifier": code,
                "identityType": 10,
                "loginDeviceId": f"ha-{self.device_id}",
                "loginDeviceJgId": "",
                "loginDeviceType": 1,
                "loginPhoneBrand": "google",
                "loginPhoneModel": "HA",
                "loginSystem": "Android",
            },
            auth=False,
        )
        if r.get("code") != "000000":
            raise GeelyAuthError(f"TSP login failed: {r.get('code')} {r.get('msg')}")
        self.access_token = r["data"]["accessToken"]
        payload = self.access_token.split(" ")[1].split(".")[1]
        payload += "=" * (-len(payload) % 4)
        self.access_token_exp = json.loads(base64.urlsafe_b64decode(payload))["exp"]
        _LOGGER.info(
            "Geely EM: logged in as %s, token valid until %s", self.email, self.access_token_exp
        )

    def ensure_session(self) -> None:
        if not self.access_token or time.time() > self.access_token_exp - 300:
            self.login()

    def vehicle_list(self) -> list[dict]:
        self.ensure_session()
        r = self._tsp_request(
            "GET", "/ms-app-bff/api/v4.0/veh/vehicle-list", params={"needSharedCar": "true"}
        )
        if r.get("code") != "000000":
            raise GeelyApiError(f"vehicle-list failed: {r.get('code')} {r.get('msg')}")
        data = r.get("data") or []
        self.vins = [v["vin"] for v in data]
        self.vehicles = data
        return data

    # ---------------- vehicle read endpoints ----------------
    def _vin_get(self, path: str, vin: str, params: dict | None = None) -> dict | list:
        r = self._tsp_request(
            "GET", path, params=params, extra_headers={"X-VIN": xvin(vin)}
        )
        if r.get("code") != "000000":
            raise GeelyApiError(f"{path} failed: {r.get('code')} {r.get('msg')}")
        return r.get("data") if r.get("data") is not None else {}

    def _vin_post(self, path: str, vin: str, json_body: dict) -> dict | list:
        r = self._tsp_request(
            "POST", path, json_body=json_body, extra_headers={"X-VIN": xvin(vin)}
        )
        if r.get("code") != "000000":
            raise GeelyApiError(f"{path} failed: {r.get('code')} {r.get('msg')}")
        return r.get("data") if r.get("data") is not None else {}

    def vehicle_status(self, vin: str) -> dict:
        return self._vin_get(
            "/ms-vehicle-status/api/v1.0/vehicle/status/latest", vin,
            params={"latest": "false", "target": "new"},
        )

    def remote_state(self, vin: str) -> dict:
        return self._vin_get("/ms-app-bff/api/v1.0/remoteControl/getVehicleState", vin)

    def charging_plan(self, vin: str) -> dict:
        return self._vin_get("/ms-charge-manage/api/v1.0/charge/getChargingPlan", vin)

    def qrvs(self, vin: str) -> dict:
        """Quick remote vehicle status: live charging values."""
        return self._vin_get(
            "/ms-vehicle-status/api/v1.0/vehicle/status/qrvs", vin,
            params={"latest": "false", "target": "new"},
        )

    def latest_soc(self, vin: str) -> dict:
        return self._vin_get("/ms-charge-manage/api/v1.0/charge/getLatestSoc", vin)

    def booking_charge(self, vin: str) -> dict:
        """Scheduled charging windows."""
        return self._vin_get("/ms-charge-manage/api/v2.0/charge/getBookingCharge", vin)

    def travel_plan(self, vin: str) -> dict:
        return self._vin_get("/ms-charge-manage/api/v1.0/charge/getLatestTravelPlan", vin)

    def ac_schedule(self, vin: str) -> dict:
        return self._vin_get("/ms-app-bff/api/v1.0/remoteControl/queryAirConSchedule", vin)

    def power_mode(self, vin: str) -> dict:
        return self._vin_get("/ms-vehicle-status/api/v1.0/vehicle/status/powerMode", vin)

    def data_usage(self, vin: str) -> dict:
        return self._vin_get("/ms-mno-service/api/v1.0/app/vehicle/data/usage/info", vin)

    def trip_list(self, vin: str, page_size: int = 20) -> dict:
        return self._vin_post(
            "/ms-vehicle-trail/v1.0/journalLog/trip/listForPage", vin,
            {"vin": vin, "pageNum": 1, "pageSize": page_size},
        )

    def fences(self, vin: str) -> list:
        data = self._vin_post(
            "/ms-vehicle-defence/v1/fence/page", vin,
            {"vin": vin, "pageNum": 1, "pageSize": 20},
        )
        return data if isinstance(data, list) else []

    def capabilities(self, vin: str) -> list:
        r = self._tsp_request(
            "GET",
            "/ms-vehicle-capability/api/v1.0/vehicle/function/model/info",
            extra_headers={"X-VIN": xvin(vin)},
        )
        if r.get("code") != "000000":
            raise GeelyApiError(f"capabilities failed: {r.get('code')} {r.get('msg')}")
        return r.get("data") or []

    # ---------------- vehicle commands ----------------
    # Payloads follow the app's command table (Cmd.kt / NetCmd.kt). None of
    # these have been checked against a live car yet.
    def _command(
        self,
        path: str,
        vin: str,
        service_id: str,
        command: str,
        params: list[tuple[str, str]] | None = None,
        duration: int | None = None,
    ) -> dict:
        self.ensure_session()
        setting: dict = {
            "serviceParameters": [{"key": k, "value": v} for k, v in params or []]
        }
        if duration is not None:
            setting["operationScheduling"] = {"duration": duration}
        body = {"command": command, "serviceId": service_id, "setting": setting}
        _LOGGER.debug("Geely EM: %s %s %s", service_id, command, setting)
        return self._vin_post(path, vin, body)

    def remote_control(self, vin: str, service_id: str, command: str, params=None, duration=None) -> dict:
        return self._command(
            "/ms-remote-control/v1.0/remoteControl/control",
            vin, service_id, command, params, duration,
        )

    def lock(self, vin: str) -> dict:
        return self.remote_control(vin, "RDL", "start", [("door", "all")])

    def unlock(self, vin: str) -> dict:
        return self.remote_control(vin, "RDU", "stop", [("door", "all")])

    def unlock_trunk(self, vin: str) -> dict:
        return self.remote_control(vin, "RDU", "stop", [("target", "trunk")])

    def open_hood(self, vin: str) -> dict:
        return self.remote_control(vin, "RDU", "start", [("target", "hood")])

    def honk_flash(self, vin: str, mode: str = "horn-light-flash") -> dict:
        """mode: horn, light-flash or horn-light-flash."""
        return self.remote_control(vin, "RHL", "start", [("rhl", mode)])

    def windows(self, vin: str, target: str, open_: bool) -> dict:
        """target: window, ventilate, sunroof, sunroofVentilate or sunshade."""
        return self.remote_control(vin, "RWS", "start" if open_ else "stop", [("target", target)])

    def remote_mode(self, vin: str, mode: str, on: bool) -> dict:
        """RSM modes: 1 parking comfort, 4 parking, 6 sentry, 8 camping."""
        return self.remote_control(vin, "RSM", "start" if on else "stop", [("rsm", mode)])

    def locate(self, vin: str) -> dict:
        """Ask the car to upload a fresh position."""
        return self.remote_control(vin, "PAI", "start", [("pai", "1")])

    def environment(self, vin: str, params: list[tuple[str, str]]) -> dict:
        """ZAF combined climate command. Keys as in EnvRegulationRequestParams:
        AC/AC.temp/AC.duration, DF/DF.level/DF.duration, SW/SW.level/SW.duration,
        SH.<pos>/SH.<pos>.level/SH.<pos>.duration (11 driver, 19 passenger,
        21 rear left, 29 rear right). Durations are minutes."""
        return self.remote_control(vin, "ZAF", "start", params)

    def charging(self, vin: str, start: bool) -> dict:
        params = [("rcs.restart", "1")] if start else [("rcs.terminate", "1")]
        return self._command(
            "/ms-charge-manage/api/v1.0/charge/control",
            vin, "RCS", "start" if start else "stop", params,
        )

    def smart_temp(self, vin: str, heat: bool, temp: float, minutes: int = 10) -> dict:
        """PAA rapid heating / cooling, as sent by the app's quick actions."""
        seats = [{"pos": "11", "level": "3"}, {"pos": "19", "level": "3"}]
        setting: dict = {
            "paa": "0",
            "duration": str(minutes * 6),
            "ac": "true",
            "temp": str(temp),
            "sw": "true" if heat else "false",
        }
        if heat:
            setting["heat"] = seats
        else:
            setting["ventilation"] = seats
        self.ensure_session()
        return self._vin_post(
            "/ms-remote-control/v1.0/remoteControl/setSmartTemp", vin,
            {"command": "immediately", "serviceId": "PAA", "setting": setting},
        )

    def set_booking_charge(self, vin: str, priority_to_soc: bool, settings: list[dict]) -> dict:
        """Write all scheduled charging slots ({id, sts, startTime, endTime})."""
        self.ensure_session()
        return self._vin_post(
            "/ms-charge-manage/api/v2.0/charge/setBookingCharge", vin,
            {
                "serviceId": "ZAZ",
                "bookingDetailSetting": {
                    "priorityToSoc": priority_to_soc,
                    "settings": settings,
                },
            },
        )

    def poll_vehicle(self, vin: str) -> dict:
        """Fetch every read endpoint for one vehicle; single failures degrade
        that section to None instead of failing the whole update."""
        out: dict[str, object] = {}
        fetches = {
            "status": self.vehicle_status,
            "remoteState": self.remote_state,
            "chargingPlan": self.charging_plan,
            "qrvs": self.qrvs,
            "latestSoc": self.latest_soc,
            "bookingCharge": self.booking_charge,
            "travelPlan": self.travel_plan,
            "acSchedule": self.ac_schedule,
            "powerMode": self.power_mode,
            "dataUsage": self.data_usage,
            "trips": self.trip_list,
        }
        for key, fn in fetches.items():
            try:
                out[key] = fn(vin)
            except GeelyApiError as exc:
                _LOGGER.debug("Geely EM: %s failed for %s: %s", key, vin, exc)
                out[key] = None
        try:
            out["fences"] = self.fences(vin)
        except GeelyApiError as exc:
            _LOGGER.debug("Geely EM: fences failed for %s: %s", vin, exc)
            out["fences"] = None
        return out
