# Geely (EM platform) for Home Assistant

Unofficial Home Assistant integration for Geely vehicles managed by the new
**Geely Global app** (Zeekr/Ecarx "EM" platform, `com.geely.global` 1.1.1+).
Verified with a Geely EX2 (VIN model code E22H-GP) in the EU region. The
read side (sensors, binary sensors, GPS tracking) is tested against a live car.
The remote commands are built from the app's own command table but have **not
been tested on a car yet**.

This integration talks directly to the same backends the mobile app uses:

| Host | Purpose |
|---|---|
| `gateway-pub-azure.zeekr.eu` | Account login (email + password, no OTP needed) |
| `eu-snc-tsp-api-gw.zeekrlife.com` | Vehicle list, status, charging plan |

## Installation (HACS)

1. Copy `custom_components/geely_em/` into `config/custom_components/` (or add
   this repo as a custom HACS repository).
2. Restart Home Assistant.
3. Settings -> Devices & Services -> Add Integration -> **Geely (EM platform)**.
4. Enter your Geely Global app email + password, your country code (e.g. `DE`)
   and language (e.g. `de`).

## What you get

Per vehicle device with:

- Battery level, charging/plugged-in, range, time to full
- **Live charging power / voltage / current** (from the quick-status endpoint)
- Last reported SOC snapshot + report time
- Scheduled charging windows (2 slots: enabled/start/end)
- Charging plan command + scheduled-charging-active flag
- Travel plan (command, departure time, pre-climatization flag)
- AC schedule (target temperature, duration)
- Odometer, trip meters, average speed, power consumption (avg + trip)
- Interior temperature, 12V battery voltage
- Tyre pressures (4x) and pressure warning, washer fluid low
- Doors, trunk, hood (open/closed), lock state
- Seat heating (driver/passenger), sunroof, window position
- Pre-climatization active, PM2.5 interior/exterior (if the car reports it)
- Parking comfort, camping mode, stranger mode, overheat protection,
  sentry mode flags
- SIM data usage (used/total)
- Trip history count, geofence count
- GPS position (device tracker), last status update time

Remote control (untested):

- Door lock
- Climate (on/off, target temperature 15.5-28.5 C, runs 15 minutes)
- Seat heating driver/passenger (off, 1-3)
- Switches: charging start/stop, defrost, steering wheel heating, parking
  comfort, camping mode, sentry mode, scheduled charging slot 1 and 2
- Start/end time of both scheduled charging slots
- Buttons: honk and flash, flash lights, unlock trunk, open front trunk, vent
  windows, close windows, rapid heating, rapid cooling, update location

Not every car supports every command. The capability catalog
(`/ms-vehicle-capability/.../function/model/info`) says what yours has; the
EX2 lists no sentry or camping mode, for example. A command the car does not
support fails with an error in Home Assistant.

## Notes

- The login flow performs an email+password login against the app backend;
  the access token lives ~7 days and is refreshed automatically before it
  expires. Every refresh mints a fresh TSP session; the phone app enforces
  single-session on its own login only.
- Polling defaults to 120 seconds (all read-only GETs). Commands are only sent
  when you use a control entity, followed by one extra refresh.
- If you use the official app at the same time it stays logged in; the EM
  platform allows parallel sessions from different clients.

## Technical summary

Everything below was recovered from the official app (XAPK decompiled with
jadx, then verified against mitmproxy captures of the live app).

### 1. Account layer (`gateway-pub-azure.zeekr.eu`)

Requests are signed with:

- `X-HMAC-SIGNATURE = Base64(HMAC-SHA256(secret, "METHOD\n/path\nquery\naccesskey\nX-DATE\n"))`
- `X-HMAC-DIGEST = Base64(HMAC-SHA256(secret, raw_body))`
- `X-DATE` = RFC 7231 GMT date
- access key + secret are build constants (from `libenv.so`)
- All `@FormUrlEncoded` calls are converted to JSON bodies before sending.

Login chain:

1. `POST /zeekr-cuc-idaas/auth/loginByEmailEncrypt` with
   `{email, codeId: "", code: "", password: RSA-OAEP? no: RSA/ECB/PKCS1(b64)}` -> `tokenValue` JWT (~90 days)
2. `POST /zeekr-cuc-idaas/user/info` -> user `uuid`
3. `GET /zeekr-cuc-idaas/user/tspCode?tspClientId=<client-id>` -> one-time `code`
4. `POST https://eu-snc-tsp-api-gw.zeekrlife.com/ms-user-auth/v1.0/auth/login`
   `{identifier: code, identityType: 10, ...}` -> `Bearer accessToken` (7 days)

### 2. Vehicle layer (`eu-snc-tsp-api-gw.zeekrlife.com`)

- `x-signature = Base64(HMAC-SHA256(secret, canonical))` with canonical:
  sorted whitelisted headers `k:v\n`, sorted query `k=v&...\n`,
  `Base64(MD5(canonical JSON body))\n`, `METHOD\n`, path.
- Whitelisted headers: `x-app-id, content-type, x-api-signature-nonce,
  x-timestamp, x-api-signature-version, x-project-id, authorization,
  accept-language, x-vin, x-device-id, x-platform` (empty `authorization` /
  `x-vin` are excluded).
- Vehicle-scoped calls additionally carry `X-VIN`:
  `Base64(AES-128-CBC-PKCS7(VIN))` with build-fixed key/iv.

### 3. Data endpoints

All polled per cycle (read-only). A failing endpoint degrades only its own
section, the rest keep updating.

- `GET /ms-app-bff/api/v4.0/veh/vehicle-list?needSharedCar=true`
- `GET /ms-vehicle-status/api/v1.0/vehicle/status/latest?latest=false&target=new`
- `GET /ms-app-bff/api/v1.0/remoteControl/getVehicleState`
- `GET /ms-charge-manage/api/v1.0/charge/getChargingPlan`
- `GET /ms-vehicle-status/api/v1.0/vehicle/status/qrvs?latest=false&target=new` (live charging values)
- `GET /ms-charge-manage/api/v1.0/charge/getLatestSoc`
- `GET /ms-charge-manage/api/v2.0/charge/getBookingCharge`
- `GET /ms-charge-manage/api/v1.0/charge/getLatestTravelPlan`
- `GET /ms-app-bff/api/v1.0/remoteControl/queryAirConSchedule`
- `GET /ms-vehicle-status/api/v1.0/vehicle/status/powerMode`
- `GET /ms-mno-service/api/v1.0/app/vehicle/data/usage/info`
- `POST /ms-vehicle-trail/v1.0/journalLog/trip/listForPage` (query)
- `POST /ms-vehicle-defence/v1/fence/page` (query)

### 4. Command endpoints

All carry the `X-VIN` header and the body
`{"command", "serviceId", "setting": {"serviceParameters": [{key, value}], "operationScheduling"?}}`.

| Feature | Endpoint | serviceId / command / params |
|---|---|---|
| Lock / unlock | `ms-remote-control/v1.0/remoteControl/control` | `RDL start door=all` / `RDU stop door=all` |
| Trunk / front trunk | same | `RDU stop target=trunk` / `RDU start target=hood` |
| Honk, flash | same | `RHL start rhl=horn-light-flash` or `light-flash` |
| Windows | same | `RWS start target=ventilate` / `RWS stop target=window` |
| Modes | same | `RSM start/stop rsm=1` parking comfort, `6` sentry, `8` camping |
| Location upload | same | `PAI start pai=1` |
| Climate, seat/wheel heat, defrost | same | `ZAF start` with `AC`, `AC.temp`, `AC.duration`, `SH.11`/`SH.19` (+`.level`, `.duration`), `SW`, `DF` |
| Charging | `ms-charge-manage/api/v1.0/charge/control` | `RCS start rcs.restart=1` / `RCS stop rcs.terminate=1` |
| Rapid heat/cool | `ms-remote-control/v1.0/remoteControl/setSmartTemp` | `PAA immediately`, object `setting` |
| Charging schedule | `ms-charge-manage/api/v2.0/charge/setBookingCharge` | `ZAZ`, full `bookingDetailSetting.settings` list |

Also available but not wired up (empty or needs car-side features enabled):
`status/carFridge`, `status/vtm`, `sentinel-monitoring-service/alarm/event/query`
(needs sentinel mode), `/ms-vehicle-capability/.../function/model/info`
(per-vehicle feature catalog).

## Roadmap

- Verify the remote commands on a live car
- Travel plan 2.0 (`setTravelPlan` v2), geofence editing, charge limit
- Only create command entities the car's capability catalog lists
- Configurable polling interval, reauth flow instead of background re-login

## Disclaimer

Unofficial. Not affiliated with Geely. Uses your own credentials against
Geely's own servers.
