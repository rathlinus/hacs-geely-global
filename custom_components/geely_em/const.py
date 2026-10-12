"""Constants for the Geely EM (Zeekr platform) integration."""
from __future__ import annotations

DOMAIN = "geely_em"

CONF_COUNTRY = "country"
CONF_LANGUAGE = "language"

DEFAULT_COUNTRY = "DE"
DEFAULT_LANGUAGE = "de"
DEFAULT_SCAN_INTERVAL = 120

# --- app platform (Geely account / user center) ---
APP_GATEWAY = "https://gateway-pub-azure.zeekr.eu/"
APP_ACCESS_KEY = "dd16247406604f91a60c1fe9a9919448"
APP_SECRET = "xmwheaz92dd4d466153b460d8ff18a5d03b59d65"
CLIENT_ID = "1JwLroFkFFIpgFGdTRrm4_nzkkwDkfHj7RxJQb7J8tc"
TMP_TENANT = "3300743799505195008"
APP_AUTH = "1026"
MSG_APP_ID = "1026"
USER_CENTER = "zeekr-cuc-idaas"
APP_VERSION = "1.1.1"

RSA_PUB = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCBzg6+dwMVtGTNo8EPL+XFyz0OY"
    "0pMMo3HdRZGauuCSgISfVMkMmOhNEb2q9UfiQcEeOwVmOgts9VF4q0BJYrRNGQaPk"
    "LybwkWsx1JmbBRcr3qq+WWhqq8xQFksfn8KeXmwgVMFX+bzup43LE0vy0yyb+SuQ9"
    "FBBGuE1d/BfHHpQIDAQAB"
)

# --- TSP platform (vehicle data) ---
TSP_GATEWAY = "https://eu-snc-tsp-api-gw.zeekrlife.com"
SNC_APP_ID = "GEELYSEACH001M0001"
SNC_PROJECT_ID = "GEELY_EU"
SNC_SECRET = "YHX0UoLjgPpYsYbhKGxlVwmFmU"
SNC_WHITELIST = (
    "x-app-id",
    "content-type",
    "x-api-signature-nonce",
    "x-timestamp",
    "x-api-signature-version",
    "x-project-id",
    "authorization",
    "accept-language",
    "x-vin",
    "x-device-id",
    "x-platform",
)

# x-vin derivation: AES-128-CBC/PKCS7 of the VIN with the app build's key/iv
XVIN_KEY = b"8a8e48ac8507d37c"
XVIN_IV = b"8be636082a956a1f"
