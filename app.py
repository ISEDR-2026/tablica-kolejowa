from __future__ import annotations

import html
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from supabase import Client, create_client

st.set_page_config(page_title="Ruch Pociągów", page_icon="🚆", layout="wide", initial_sidebar_state="collapsed")

PROFILE_ID = "adrian"
API = "https://pdp-api.plk-sa.pl/api/v1"
TZ = ZoneInfo("Europe/Warsaw")
TIMEOUT = 30
TRAINS_TTL = 90
STATIONS_TTL = 86400
DETAILS_TTL = 21600
PASS_THROUGH_MAX_SECONDS = 30
TRAIN_LIMITS = [5, 10, 15]
DEFAULT_FAVORITES = ["Kamień Pomorski", "Wysoka Kamieńska", "Gryfice", "Goleniów"]

st.markdown("""
<style>
.block-container{max-width:1180px;padding-top:2.2rem;padding-bottom:2rem}
.title{font-size:2.3rem;font-weight:800;line-height:1.1}.sub{color:#a8adb7;margin:.2rem 0 1rem}
.banner{border-radius:10px;padding:.7rem .9rem;margin-bottom:1rem}.ok{background:rgba(46,160,67,.14);border:1px solid rgba(46,160,67,.38)}
.warn{background:rgba(255,179,71,.12);border:1px solid rgba(255,179,71,.35)}.err{background:rgba(220,53,69,.13);border:1px solid rgba(220,53,69,.35)}
.station{font-size:1.4rem;font-weight:750}.muted{color:#a8adb7;font-size:.84rem}.time{font-size:2rem;font-weight:800;line-height:1}
.times{font-size:.9rem;margin:.3rem 0}.train{font-size:1.08rem;font-weight:800}.relation{font-size:.98rem;font-weight:650;margin:.18rem 0 .35rem}
.track{display:inline-block;margin-top:.45rem;padding:.38rem .58rem;border-radius:8px;background:rgba(255,255,255,.075);border:1px solid rgba(255,255,255,.14);font-size:.88rem;font-weight:750}
.row{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.46rem}.pill{display:inline-block;padding:.3rem .56rem;border-radius:8px;font-size:.78rem;font-weight:700}
.stop{background:rgba(46,160,67,.15);color:#8ef0a9;border:1px solid rgba(46,160,67,.28)}.pass{background:rgba(65,130,220,.17);color:#a9d1ff;border:1px solid rgba(65,130,220,.3)}
.start{background:rgba(155,89,182,.16);color:#d8b4f2;border:1px solid rgba(155,89,182,.3)}.end{background:rgba(230,126,34,.15);color:#ffc58e;border:1px solid rgba(230,126,34,.3)}
.neutral{background:rgba(255,255,255,.065);color:#dce1ea;border:1px solid rgba(255,255,255,.12)}
.eta-label{text-align:right;color:#a8adb7;font-size:.76rem}.eta{text-align:right;font-size:1.35rem;font-weight:800}.status{text-align:right;margin-top:.35rem}
.status span{display:inline-block;padding:.4rem .65rem;border-radius:10px;font-size:.82rem;font-weight:700}.sok{background:rgba(46,160,67,.22);color:#8ef0a9}.swarn{background:rgba(190,150,20,.22);color:#ffd86a}.searly{background:rgba(65,130,220,.2);color:#9cc8ff}.splan{background:rgba(255,255,255,.07);color:#dce1ea}
.note{text-align:right;color:#a8adb7;font-size:.74rem;margin-top:.35rem}div[data-testid="stButton"]>button{min-height:2.65rem;border-radius:10px;font-weight:650}div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:14px}
@media(max-width:640px){.title{font-size:1.95rem}.time{font-size:1.65rem}.train{font-size:1rem}.eta{font-size:1.1rem}}
</style>
""", unsafe_allow_html=True)


def now() -> datetime:
    return datetime.now(TZ)


def parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt.astimezone(TZ)


def parse_generated(value: Any) -> datetime | None:
    dt = parse_dt(value)
    return dt


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def dict_value(data: Any, key: Any, default: str = "") -> str:
    if not isinstance(data, dict):
        return default
    value = data.get(str(key), data.get(key))
    return default if value in (None, "") else str(value)


def route_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return tuple(str(record.get(k, "")) for k in ("scheduleId", "orderId", "trainOrderId"))


def delay_minutes(planned: datetime | None, actual: datetime | None, api_value: Any) -> int | None:
    if api_value not in (None, ""):
        return safe_int(api_value)
    if planned is None or actual is None:
        return None
    return round((actual - planned).total_seconds() / 60)


def fmt_clock(value: datetime | None, seconds: bool = False) -> str:
    if value is None:
        return "—"
    return value.strftime("%H:%M:%S" if seconds or value.second else "%H:%M")


def fmt_delay(value: int | None) -> str:
    if value is None:
        return "brak danych"
    if value > 0:
        return f"+{value} min"
    if value < 0:
        return f"{value} min"
    return "0 min"


def fmt_duration(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes, rest = divmod(seconds, 60)
    return f"{minutes} min" if rest == 0 else f"{minutes} min {rest} s"


def supabase_client() -> Client | None:
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as error:
        st.error("Nie udało się połączyć z Supabase.")
        st.caption(str(error))
        return None


supabase = supabase_client()


def load_settings() -> tuple[list[str], str]:
    if supabase is None:
        return DEFAULT_FAVORITES.copy(), DEFAULT_FAVORITES[0]
    try:
        result = (supabase.table("train_app_settings").select("favorites, selected_station").eq("profile_id", PROFILE_ID).limit(1).execute())
        if result.data:
            row = result.data[0]
            favorites = row.get("favorites") or DEFAULT_FAVORITES.copy()
            favorites = [str(x) for x in favorites if str(x).strip()] if isinstance(favorites, list) else DEFAULT_FAVORITES.copy()
            return favorites or DEFAULT_FAVORITES.copy(), str(row.get("selected_station") or favorites[0])
    except Exception as error:
        st.warning("Nie udało się odczytać ustawień. Używam wartości domyślnych.")
        st.caption(str(error))
    return DEFAULT_FAVORITES.copy(), DEFAULT_FAVORITES[0]


def save_settings() -> bool:
    if supabase is None:
        return False
    try:
        supabase.table("train_app_settings").upsert({
            "profile_id": PROFILE_ID,
            "favorites": st.session_state.favorites,
            "selected_station": st.session_state.selected_station,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="profile_id").execute()
        st.session_state.settings_error = ""
        return True
    except Exception as error:
        st.session_state.settings_error = str(error)
        return False


def headers() -> dict[str, str]:
    return {"X-API-Key": str(st.secrets["PKP_API_KEY"]).strip(), "Accept": "application/json"}


def request_api(endpoint: str, params: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, int, str]:
    try:
        response = requests.get(f"{API}{endpoint}", headers=headers(), params=params, timeout=TIMEOUT)
    except requests.RequestException as error:
        return None, 0, str(error)
    if response.status_code != 200:
        try:
            body = response.json()
            message = body.get("message") or body.get("messageEn") or body.get("error") or response.text
        except ValueError:
            message = response.text
        return None, response.status_code, str(message)[:600]
    try:
        body = response.json()
    except ValueError:
        return None, response.status_code, "API zwróciło odpowiedź inną niż JSON."
    return (body, response.status_code, "") if isinstance(body, dict) else (None, response.status_code, "Nieoczekiwana struktura danych.")


@st.cache_data(ttl=STATIONS_TTL, show_spinner=False)
def get_all_stations() -> tuple[list[dict[str, Any]], int, str]:
    body, status, error = request_api("/dictionaries/stations", {"page": 1, "pageSize": 10000})
    if body is None:
        return [], status, error
    stations, seen = [], set()
    for item in body.get("stations", []):
        if not isinstance(item, dict):
            continue
        station_id, name = safe_int(item.get("id"), -1), str(item.get("name", "")).strip()
        key = (station_id, norm(name))
        if station_id >= 0 and name and key not in seen:
            seen.add(key)
            stations.append({"id": station_id, "name": name})
    stations.sort(key=lambda x: norm(x["name"]))
    return stations, 200, ""


@st.cache_data(ttl=TRAINS_TTL, show_spinner=False)
def get_operations(station_id: int):
    return request_api("/operations", {"stations": station_id, "withPlanned": "true", "fullRoutes": "true", "page": 1, "pageSize": 1000})


@st.cache_data(ttl=TRAINS_TTL, show_spinner=False)
def get_schedules(station_id: int, date_from: str, date_to: str):
    return request_api("/schedules", {"stations": station_id, "dateFrom": date_from, "dateTo": date_to, "page": 1, "pageSize": 1000})


@st.cache_data(ttl=DETAILS_TTL, show_spinner=False)
def get_route_details(schedule_id: Any, order_id: Any):
    return request_api(f"/schedules/route/{schedule_id}/{order_id}")


def station_indexes(records: list[dict[str, Any]]) -> tuple[dict[str, int], dict[int, str], list[str]]:
    name_to_id, id_to_name, names, used = {}, {}, [], set()
    for item in records:
        station_id, base = safe_int(item["id"]), str(item["name"]).strip()
        display = base if base not in used else f"{base} [{station_id}]"
        used.add(display)
        name_to_id[display], id_to_name[station_id] = station_id, base
        names.append(display)
    return name_to_id, id_to_name, names


def find_point(train: dict[str, Any], station_id: int) -> dict[str, Any] | None:
    for point in train.get("stations", []):
        if isinstance(point, dict) and safe_int(point.get("stationId")) == station_id:
            return point
    return None


def get_name(station_id: int, operations_map: dict[str, Any], global_map: dict[int, str]) -> str:
    return dict_value(operations_map, station_id, global_map.get(station_id, f"Stacja {station_id}"))


def relation(train: dict[str, Any], operations_map: dict[str, Any], global_map: dict[int, str]) -> str:
    points = [p for p in train.get("stations", []) if isinstance(p, dict) and p.get("stationId") is not None]
    if not points:
        return "Relacja nieznana"
    first, last = safe_int(points[0].get("stationId")), safe_int(points[-1].get("stationId"))
    return f"{get_name(first, operations_map, global_map)} → {get_name(last, operations_map, global_map)}"


def classify(point: dict[str, Any]) -> tuple[str, str, str, int | None]:
    arr, dep = parse_dt(point.get("plannedArrival")), parse_dt(point.get("plannedDeparture"))
    if arr is None and dep is not None:
        return "Stacja początkowa", "🚉", "start", None
    if arr is not None and dep is None:
        return "Stacja końcowa", "🏁", "end", None
    if arr is not None and dep is not None:
        dwell = max(0, int((dep - arr).total_seconds()))
        return ("Przejazd bez postoju", "➡️", "pass", dwell) if dwell <= PASS_THROUGH_MAX_SECONDS else ("Postój", "🛑", "stop", dwell)
    return "Punkt trasy", "📍", "pass", None


def last_confirmed(train: dict[str, Any], station_id: int, operations_map: dict[str, Any], global_map: dict[int, str]) -> tuple[str, datetime | None]:
    points = train.get("stations", [])
    selected_index = next((i for i, p in enumerate(points) if isinstance(p, dict) and safe_int(p.get("stationId")) == station_id), len(points) - 1)
    for point in reversed(points[:selected_index + 1]):
        if isinstance(point, dict) and point.get("isConfirmed"):
            sid = safe_int(point.get("stationId"), -1)
            if sid >= 0:
                return get_name(sid, operations_map, global_map), parse_dt(point.get("actualDeparture")) or parse_dt(point.get("actualArrival"))
    return "", None


def convert_train(train: dict[str, Any], route: dict[str, Any] | None, station_id: int, operations_map: dict[str, Any], global_map: dict[int, str], dictionaries: dict[str, Any]) -> dict[str, Any] | None:
    point = find_point(train, station_id)
    if point is None:
        return None

    movement, icon, css, planned_dwell = classify(point)
    pa, pd = parse_dt(point.get("plannedArrival")), parse_dt(point.get("plannedDeparture"))
    aa, ad = parse_dt(point.get("actualArrival")), parse_dt(point.get("actualDeparture"))

    if movement == "Stacja początkowa":
        planned_ref, actual_ref, event = pd, ad or pd, "odjazd"
    elif movement == "Stacja końcowa":
        planned_ref, actual_ref, event = pa, aa or pa, "przyjazd"
    elif movement == "Przejazd bez postoju":
        planned_ref, actual_ref, event = pa or pd, aa or ad or pa or pd, "przejazd"
    else:
        planned_ref, actual_ref, event = pa or pd, aa or ad or pa or pd, "przyjazd"
    if planned_ref is None or actual_ref is None:
        return None

    schedule_point = find_point(route, station_id) if isinstance(route, dict) else None
    carriers, categories, stop_types = dictionaries.get("carriers", {}), dictionaries.get("commercialCategories", {}), dictionaries.get("stopTypes", {})
    carrier_code = str(route.get("carrierCode", "")) if isinstance(route, dict) else ""
    category_symbol = str(route.get("commercialCategorySymbol", "")) if isinstance(route, dict) else ""
    national_number = str(route.get("nationalNumber", "")) if isinstance(route, dict) else ""
    if not national_number:
        national_number = str(train.get("trainOrderId", "—"))
    train_number = " ".join(x for x in (category_symbol, national_number) if x).strip()

    platform, track, restriction = "—", "", ""
    if isinstance(schedule_point, dict):
        if movement == "Stacja końcowa":
            platform = str(schedule_point.get("arrivalPlatform", schedule_point.get("departurePlatform", "—")))
            track = str(schedule_point.get("arrivalTrack", schedule_point.get("departureTrack", "")))
        else:
            platform = str(schedule_point.get("departurePlatform", schedule_point.get("arrivalPlatform", "—")))
            track = str(schedule_point.get("departureTrack", schedule_point.get("arrivalTrack", "")))
        stop_type = schedule_point.get("stopType") or schedule_point.get("arrivalStopType") or schedule_point.get("departureStopType")
        if stop_type not in (None, ""):
            restriction = dict_value(stop_types, stop_type)

    arr_delay = delay_minutes(pa, aa, point.get("arrivalDelayMinutes"))
    dep_delay = delay_minutes(pd, ad, point.get("departureDelayMinutes"))
    reference_delay = dep_delay if event == "odjazd" else (arr_delay if arr_delay is not None else dep_delay)
    actual_dwell = max(0, int((ad - aa).total_seconds())) if aa is not None and ad is not None else None
    confirmed_station, confirmed_time = last_confirmed(train, station_id, operations_map, global_map)

    return {
        "schedule_id": train.get("scheduleId"), "order_id": train.get("orderId"), "train_order_id": train.get("trainOrderId"),
        "planned_ref": planned_ref, "actual_ref": actual_ref, "event": event, "minutes_until": max(0, int((actual_ref - now()).total_seconds() // 60)),
        "planned_arrival": pa, "planned_departure": pd, "actual_arrival": aa, "actual_departure": ad,
        "arrival_delay": arr_delay, "departure_delay": dep_delay, "reference_delay": reference_delay,
        "relation": relation(train, operations_map, global_map), "train_number": train_number or "—", "train_name": "",
        "carrier": dict_value(carriers, carrier_code, carrier_code or "Przewoźnik nieznany"),
        "category": dict_value(categories, category_symbol, category_symbol), "platform": platform, "track": track,
        "movement": movement, "icon": icon, "movement_css": css, "planned_dwell": planned_dwell, "actual_dwell": actual_dwell,
        "restriction": restriction, "confirmed": bool(point.get("isConfirmed", False)),
        "last_confirmed_station": confirmed_station, "last_confirmed_time": confirmed_time,
    }


@st.cache_data(ttl=TRAINS_TTL, show_spinner=False)
def get_live_trains(station_id: int, global_map: dict[int, str], limit: int):
    today = now().date()
    operations, op_status, op_error = get_operations(station_id)
    if operations is None:
        return [], "error", op_status, op_error, None
    schedules, sc_status, sc_error = get_schedules(station_id, today.isoformat(), (today + timedelta(days=1)).isoformat())
    if schedules is None:
        return [], "error", sc_status, sc_error, parse_generated(operations.get("generatedAt"))

    routes = {route_key(r): r for r in schedules.get("routes", []) if isinstance(r, dict)}
    dictionaries = schedules.get("dictionaries", {}) if isinstance(schedules.get("dictionaries", {}), dict) else {}
    operations_map = operations.get("stations", {}) if isinstance(operations.get("stations", {}), dict) else {}
    cutoff, converted = now() - timedelta(minutes=2), []

    for item in operations.get("trains", []):
        if not isinstance(item, dict):
            continue
        converted_item = convert_train(item, routes.get(route_key(item)), station_id, operations_map, global_map, dictionaries)
        if converted_item and converted_item["actual_ref"] >= cutoff:
            converted.append(converted_item)

    converted.sort(key=lambda x: x["actual_ref"])
    unique, seen = [], set()
    for item in converted:
        key = (str(item["train_order_id"]), item["actual_ref"].strftime("%Y-%m-%d %H:%M:%S"), item["relation"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    selected = unique[:limit]
    for item in selected:
        details, _, _ = get_route_details(item["schedule_id"], item["order_id"])
        if isinstance(details, dict):
            item["train_name"] = " ".join(str(details.get("name") or "").split())

    return selected, "live", 200, "", parse_generated(operations.get("generatedAt"))


with st.spinner("Pobieram listę stacji PKP PLK…"):
    station_records, stations_status, stations_error = get_all_stations()

if station_records:
    station_name_to_id, station_id_to_name, station_names = station_indexes(station_records)
else:
    station_name_to_id, station_id_to_name, station_names = {}, {}, DEFAULT_FAVORITES.copy()

if "settings_loaded" not in st.session_state:
    favorites, selected = load_settings()
    st.session_state.favorites = favorites
    st.session_state.selected_station = selected
    st.session_state.train_limit = 5
    st.session_state.settings_error = ""
    st.session_state.settings_loaded = True

st.session_state.favorites = [x for x in st.session_state.favorites if x in station_names] or [x for x in DEFAULT_FAVORITES if x in station_names] or station_names[:1]
if st.session_state.selected_station not in station_names:
    st.session_state.selected_station = st.session_state.favorites[0]
if st.session_state.train_limit not in TRAIN_LIMITS:
    st.session_state.train_limit = 5


def choose_station(name: str) -> None:
    st.session_state.selected_station = name
    save_settings()


def change_station() -> None:
    choose_station(st.session_state.main_station_selector)


def add_favorite() -> None:
    name = st.session_state.station_to_add
    if name and name not in st.session_state.favorites:
        st.session_state.favorites.append(name)
        save_settings()


def remove_favorite(name: str) -> None:
    if len(st.session_state.favorites) <= 1:
        return
    if name in st.session_state.favorites:
        st.session_state.favorites.remove(name)
    if st.session_state.selected_station == name:
        st.session_state.selected_station = st.session_state.favorites[0]
    save_settings()


with st.sidebar:
    st.header("⚙️ Ustawienia")
    if supabase is not None:
        st.success("Połączono z Supabase", icon="✅")
    if station_records:
        st.success(f"Załadowano stacje: {len(station_names)}", icon="🚉")
    else:
        st.error("Nie udało się pobrać listy stacji.")
        if stations_error:
            st.caption(stations_error)

    st.subheader("Widok tablicy")
    st.selectbox("Liczba najbliższych pociągów:", TRAIN_LIMITS, key="train_limit")
    st.subheader("Ulubione stacje")
    available_to_add = [x for x in station_names if x not in st.session_state.favorites]
    if available_to_add:
        st.selectbox("Dodaj stację:", available_to_add, key="station_to_add")
        st.button("➕ Dodaj do ulubionych", on_click=add_favorite, use_container_width=True)
    for i, name in enumerate(st.session_state.favorites.copy()):
        left, right = st.columns([3, 1])
        with left:
            st.write(f"⭐ {name}")
        with right:
            st.button("✕", key=f"remove_{i}_{name}", on_click=remove_favorite, args=(name,), disabled=len(st.session_state.favorites) <= 1)
    st.divider()
    if st.button("🔄 Odśwież dane PKP", use_container_width=True):
        get_live_trains.clear(); get_operations.clear(); get_schedules.clear(); get_route_details.clear()
    if st.button("🔄 Odśwież listę stacji", use_container_width=True):
        get_all_stations.clear()
    st.caption(f"Dane pociągów są buforowane przez {TRAINS_TTL} sekund.")
    if st.session_state.settings_error:
        st.error("Nie udało się zapisać ustawień.")
        st.caption(st.session_state.settings_error)

st.markdown('<div class="title">🚆 Ruch Pociągów</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">Techniczna tablica ruchu dla wybranej stacji</div>', unsafe_allow_html=True)

head_left, head_right = st.columns([3, 1])
with head_left:
    st.subheader("⭐ Ulubione stacje")
with head_right:
    st.caption("☰ Edycja w panelu bocznym")

favorite_columns = st.columns(min(4, max(1, len(st.session_state.favorites))))
for i, name in enumerate(st.session_state.favorites):
    with favorite_columns[i % len(favorite_columns)]:
        selected = name == st.session_state.selected_station
        st.button(f"✓ {name}" if selected else name, key=f"fav_{i}_{name}", type="primary" if selected else "secondary", on_click=choose_station, args=(name,), use_container_width=True)

selected_index = station_names.index(st.session_state.selected_station) if st.session_state.selected_station in station_names else 0
st.selectbox("🔎 Wybierz dowolną stację:", station_names, index=selected_index, key="main_station_selector", on_change=change_station)

selected_station = st.session_state.selected_station
selected_id = station_name_to_id.get(selected_station)
if selected_id is None:
    trains, mode, status, error, generated = [], "error", 404, "Nie znaleziono identyfikatora stacji.", None
else:
    with st.spinner(f"Pobieram ruch pociągów dla stacji {selected_station}…"):
        trains, mode, status, error, generated = get_live_trains(selected_id, station_id_to_name, st.session_state.train_limit)

if mode == "live" and trains:
    st.markdown('<div class="banner ok">✅ <strong>Dane rzeczywiste PKP PLK</strong> — wyświetlane są najbliższe pociągi.</div>', unsafe_allow_html=True)
elif mode == "live":
    st.markdown('<div class="banner warn">ℹ️ Połączono z API, ale nie znaleziono nadchodzących pociągów.</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="banner err">⚠️ <strong>Nie udało się pobrać danych PKP.</strong></div>', unsafe_allow_html=True)
    if error:
        st.code(error)

update_time = generated or now()
with st.container(border=True):
    st.markdown(f'<div class="station">🚉 {html.escape(selected_station)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="muted">Ostatnia aktualizacja: {update_time:%H:%M:%S} · pozycje: {len(trains)}</div>', unsafe_allow_html=True)

if not trains:
    st.info("Brak nadchodzących pociągów dla wybranej stacji.")

for train in trains:
    with st.container(border=True):
        left, right = st.columns([3.3, 1])
        with left:
            seconds = train["movement"] == "Przejazd bez postoju" or train["actual_ref"].second != 0
            st.markdown(f'<div class="time">{fmt_clock(train["actual_ref"], seconds)}</div>', unsafe_allow_html=True)
            time_parts = []
            if train["planned_arrival"] is not None:
                time_parts.append(f'Przyjazd {fmt_clock(train["planned_arrival"])} ({fmt_delay(train["arrival_delay"])})')
            if train["planned_departure"] is not None:
                time_parts.append(f'Odjazd {fmt_clock(train["planned_departure"])} ({fmt_delay(train["departure_delay"])})')
            if time_parts:
                st.markdown(f'<div class="times">{html.escape(" · ".join(time_parts))}</div>', unsafe_allow_html=True)

            title = train["train_number"]
            if train["train_name"]:
                title += f' · „{train["train_name"]}”'
            st.markdown(f'<div class="train">{html.escape(title)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="relation">{html.escape(train["relation"])}</div>', unsafe_allow_html=True)
            details = [train["carrier"]]
            if train["category"]:
                details.append(train["category"])
            if train["restriction"]:
                details.append(train["restriction"])
            st.markdown(f'<div class="muted">{html.escape(" · ".join(details))}</div>', unsafe_allow_html=True)

            track_parts = []
            if train["platform"] and train["platform"] != "—":
                track_parts.append(f'Peron {train["platform"]}')
            if train["track"]:
                track_parts.append(f'Tor {train["track"]}')
            if track_parts:
                st.markdown(f'<div class="track">🚦 {html.escape(" · ".join(track_parts))}</div>', unsafe_allow_html=True)

            pills = [f'<span class="pill {train["movement_css"]}">{train["icon"]} {html.escape(train["movement"])}</span>']
            if train["planned_dwell"] is not None:
                pills.append(f'<span class="pill neutral">⏱️ Postój planowy: {html.escape(fmt_duration(train["planned_dwell"]))}</span>')
            if train["actual_dwell"] is not None and train["movement"] == "Postój":
                pills.append(f'<span class="pill neutral">📏 Postój rzeczywisty: {html.escape(fmt_duration(train["actual_dwell"]))}</span>')
            pills.append('<span class="pill neutral">✅ Dane potwierdzone</span>' if train["confirmed"] else '<span class="pill neutral">◌ Dane planowe</span>')
            st.markdown('<div class="row">' + ''.join(pills) + '</div>', unsafe_allow_html=True)

        with right:
            st.markdown(f'<div class="eta-label">{html.escape(train["event"].capitalize())}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="eta">za {train["minutes_until"]} min</div>', unsafe_allow_html=True)
            delay = train["reference_delay"]
            if delay is None:
                status_html = '<span class="splan">◌ Brak danych rzeczywistych</span>'
            elif delay == 0:
                status_html = '<span class="sok">✅ Punktualnie</span>'
            elif delay > 0:
                status_html = f'<span class="swarn">⚠️ Opóźnienie +{delay} min</span>'
            else:
                status_html = f'<span class="searly">ℹ️ Przed czasem {abs(delay)} min</span>'
            st.markdown(f'<div class="status">{status_html}</div>', unsafe_allow_html=True)
            if train["last_confirmed_station"]:
                note = f'Ostatnio potwierdzony:<br><strong>{html.escape(train["last_confirmed_station"])}</strong>'
                if train["last_confirmed_time"] is not None:
                    note += f' · {train["last_confirmed_time"]:%H:%M:%S}'
                st.markdown(f'<div class="note">{note}</div>', unsafe_allow_html=True)

st.caption("Dane: PKP Polskie Linie Kolejowe S.A. • nazwy pociągów pobierane ze szczegółów trasy • przejazd bez postoju rozpoznawany jako punkt techniczny do 30 sekund")
