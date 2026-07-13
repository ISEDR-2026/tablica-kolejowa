from __future__ import annotations

import html
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from supabase import Client, create_client

st.set_page_config(page_title="MINI SWDR", page_icon="🚆", layout="wide", initial_sidebar_state="collapsed")

PROFILE_ID = "adrian"
API = "https://pdp-api.plk-sa.pl/api/v1"
TZ = ZoneInfo("Europe/Warsaw")
TIMEOUT = 30
TRAINS_TTL = 90
STATIONS_TTL = 86400
DETAILS_TTL = 21600
TRAIN_LIMITS = [5, 10, 15]
DEFAULT_FAVORITES = ["Kamień Pomorski", "Wysoka Kamieńska", "Gryfice", "Goleniów"]

st.markdown("""
<style>
.block-container{max-width:1180px;padding-top:5.2rem;padding-bottom:2rem}
.app-header{display:flex;align-items:center;gap:1rem;padding:1rem 1.1rem;margin:0 0 1.25rem;border:1px solid rgba(255,255,255,.12);border-left:5px solid #ef233c;border-radius:14px;background:linear-gradient(135deg,rgba(24,31,42,.96),rgba(12,17,24,.94));box-shadow:0 8px 24px rgba(0,0,0,.22)}
.signal-stack{display:flex;flex-direction:column;gap:.22rem;padding:.38rem .44rem;border-radius:10px;background:#090d12;border:1px solid rgba(255,255,255,.12)}
.signal-dot{width:.6rem;height:.6rem;border-radius:50%;display:block}.signal-red{background:#ef233c;box-shadow:0 0 8px rgba(239,35,60,.65)}.signal-amber{background:#f6c344;box-shadow:0 0 8px rgba(246,195,68,.48)}.signal-green{background:#42d17d;box-shadow:0 0 8px rgba(66,209,125,.48)}
.title{font-size:2.3rem;font-weight:850;line-height:1.08;letter-spacing:.06em;margin:0}.subtitle{color:#a8adb7;font-size:.96rem;margin-top:.28rem}
.rail-divider{height:4px;margin:-.72rem 0 1.35rem;border-radius:999px;background:repeating-linear-gradient(90deg,#3c4654 0 26px,#141a22 26px 34px)}
.station{font-size:1.4rem;font-weight:750;letter-spacing:.02em}.muted{color:#a8adb7;font-size:.84rem}.time{font-size:2rem;font-weight:800;line-height:1}
.times{font-size:.9rem;margin:.3rem 0}.train{font-size:1.08rem;font-weight:800}.relation{font-size:.98rem;font-weight:650;margin:.18rem 0 .35rem}
.track{display:inline-block;margin-top:.45rem;padding:.38rem .58rem;border-radius:8px;background:rgba(255,255,255,.075);border:1px solid rgba(255,255,255,.14);border-left:3px solid #ef233c;font-size:.88rem;font-weight:750;letter-spacing:.02em}
.row{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.46rem}.pill{display:inline-block;padding:.3rem .56rem;border-radius:8px;font-size:.78rem;font-weight:700}
.start{background:rgba(155,89,182,.16);color:#d8b4f2;border:1px solid rgba(155,89,182,.3)}.end{background:rgba(230,126,34,.15);color:#ffc58e;border:1px solid rgba(230,126,34,.3)}.neutral{background:rgba(255,255,255,.065);color:#dce1ea;border:1px solid rgba(255,255,255,.12)}
.eta-label{text-align:right;color:#a8adb7;font-size:.76rem}.eta{text-align:right;font-size:1.35rem;font-weight:800}.status{text-align:right;margin-top:.35rem}
.status span{display:inline-block;padding:.4rem .65rem;border-radius:10px;font-size:.82rem;font-weight:700}.sok{background:rgba(46,160,67,.22);color:#8ef0a9}.swarn{background:rgba(190,150,20,.22);color:#ffd86a}.searly{background:rgba(65,130,220,.2);color:#9cc8ff}.splan{background:rgba(255,255,255,.07);color:#dce1ea}
.note{text-align:right;color:#a8adb7;font-size:.74rem;margin-top:.35rem}
.route-summary{color:#a8adb7;font-size:.84rem;margin:.15rem 0 .7rem}
.route-list{display:flex;flex-direction:column;gap:.48rem;margin:.25rem 0 .5rem}
.route-stop{display:grid;grid-template-columns:2rem minmax(150px,1.35fr) minmax(220px,2fr);gap:.65rem;align-items:center;padding:.58rem .68rem;border-radius:10px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.035)}
.route-stop.passed{border-left:4px solid #42d17d}.route-stop.current{border-left:4px solid #f6c344;background:rgba(246,195,68,.07)}.route-stop.future{border-left:4px solid #667080}
.route-icon{font-size:1.12rem;text-align:center}.route-name{font-weight:750;line-height:1.2}.route-meta{color:#a8adb7;font-size:.78rem;margin-top:.14rem}.route-times{font-size:.82rem;line-height:1.45}.route-delay-ok{color:#8ef0a9;font-weight:700}.route-delay-warn{color:#ffd86a;font-weight:700}.route-estimate{color:#a9d1ff;font-weight:700}
div[data-testid="stButton"]>button{min-height:2.65rem;border-radius:10px;font-weight:650}div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:14px}
@media(max-width:640px){.block-container{padding-top:4.5rem}.app-header{padding:.85rem .9rem}.title{font-size:1.85rem}.time{font-size:1.65rem}.train{font-size:1rem}.eta{font-size:1.1rem}.route-stop{grid-template-columns:1.7rem 1fr}.route-times{grid-column:2}}
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


def fmt_clock(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%H:%M")


def fmt_delay(value: int | None) -> str:
    if value is None:
        return "brak danych"
    if value > 0:
        return f"+{value} min"
    if value < 0:
        return f"{value} min"
    return "0 min"


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


def endpoint_status(point: dict[str, Any]) -> tuple[str, str, str]:
    arr = parse_dt(point.get("plannedArrival"))
    dep = parse_dt(point.get("plannedDeparture"))
    if arr is None and dep is not None:
        return "Stacja początkowa", "🚉", "start"
    if arr is not None and dep is None:
        return "Stacja końcowa", "🏁", "end"
    return "", "", ""


def last_confirmed(train: dict[str, Any], station_id: int, operations_map: dict[str, Any], global_map: dict[int, str]) -> tuple[str, datetime | None]:
    points = train.get("stations", [])
    selected_index = next((i for i, p in enumerate(points) if isinstance(p, dict) and safe_int(p.get("stationId")) == station_id), len(points) - 1)
    for point in reversed(points[:selected_index + 1]):
        if isinstance(point, dict) and point.get("isConfirmed"):
            sid = safe_int(point.get("stationId"), -1)
            if sid >= 0:
                return get_name(sid, operations_map, global_map), parse_dt(point.get("actualDeparture")) or parse_dt(point.get("actualArrival"))
    return "", None



def add_delay(value: datetime | None, delay: int | None) -> datetime | None:
    if value is None:
        return None
    if delay is None:
        return value
    return value + timedelta(minutes=delay)


def build_route_timeline(
    operation_points: list[dict[str, Any]],
    schedule_points: list[dict[str, Any]],
    operations_map: dict[str, Any],
    global_map: dict[int, str],
    selected_station_id: int,
) -> tuple[list[dict[str, Any]], int | None]:
    schedule_by_station = {
        safe_int(point.get("stationId")): point
        for point in schedule_points
        if isinstance(point, dict) and point.get("stationId") is not None
    }

    last_confirmed_index = -1
    current_delay: int | None = None

    for index, point in enumerate(operation_points):
        if not isinstance(point, dict):
            continue

        if point.get("isConfirmed"):
            last_confirmed_index = index

            planned_departure = parse_dt(point.get("plannedDeparture"))
            actual_departure = parse_dt(point.get("actualDeparture"))
            planned_arrival = parse_dt(point.get("plannedArrival"))
            actual_arrival = parse_dt(point.get("actualArrival"))

            departure_delay = delay_minutes(
                planned_departure,
                actual_departure,
                point.get("departureDelayMinutes"),
            )
            arrival_delay = delay_minutes(
                planned_arrival,
                actual_arrival,
                point.get("arrivalDelayMinutes"),
            )

            current_delay = (
                departure_delay
                if departure_delay is not None
                else arrival_delay
            )

    timeline: list[dict[str, Any]] = []

    for index, point in enumerate(operation_points):
        if not isinstance(point, dict):
            continue

        station_id = safe_int(point.get("stationId"), -1)
        if station_id < 0:
            continue

        schedule_point = schedule_by_station.get(station_id, {})
        planned_arrival = parse_dt(point.get("plannedArrival"))
        planned_departure = parse_dt(point.get("plannedDeparture"))
        actual_arrival = parse_dt(point.get("actualArrival"))
        actual_departure = parse_dt(point.get("actualDeparture"))

        arrival_delay = delay_minutes(
            planned_arrival,
            actual_arrival,
            point.get("arrivalDelayMinutes"),
        )
        departure_delay = delay_minutes(
            planned_departure,
            actual_departure,
            point.get("departureDelayMinutes"),
        )

        if index < last_confirmed_index:
            status = "passed"
        elif index == last_confirmed_index and last_confirmed_index >= 0:
            status = "current"
        else:
            status = "future"

        estimated_arrival = None
        estimated_departure = None

        if status == "future" and current_delay is not None:
            estimated_arrival = add_delay(planned_arrival, current_delay)
            estimated_departure = add_delay(planned_departure, current_delay)

        platform = str(
            schedule_point.get(
                "departurePlatform",
                schedule_point.get("arrivalPlatform", ""),
            )
            or ""
        )
        track = str(
            schedule_point.get(
                "departureTrack",
                schedule_point.get("arrivalTrack", ""),
            )
            or ""
        )

        timeline.append(
            {
                "station_id": station_id,
                "name": get_name(station_id, operations_map, global_map),
                "selected": station_id == selected_station_id,
                "status": status,
                "planned_arrival": planned_arrival,
                "planned_departure": planned_departure,
                "actual_arrival": actual_arrival if point.get("isConfirmed") else None,
                "actual_departure": actual_departure if point.get("isConfirmed") else None,
                "arrival_delay": arrival_delay if point.get("isConfirmed") else None,
                "departure_delay": departure_delay if point.get("isConfirmed") else None,
                "estimated_arrival": estimated_arrival,
                "estimated_departure": estimated_departure,
                "platform": platform,
                "track": track,
                "confirmed": bool(point.get("isConfirmed")),
            }
        )

    return timeline, current_delay


def delay_css(value: int | None) -> str:
    if value is None or value == 0:
        return "route-delay-ok"
    return "route-delay-warn"


def render_route_timeline(train: dict[str, Any]) -> None:
    timeline = train.get("route_timeline", [])

    if not timeline:
        st.info("Brak szczegółowych danych o pełnej trasie tego pociągu.")
        return

    current_delay = train.get("route_current_delay")
    summary_parts = [
        f"Liczba punktów trasy: {len(timeline)}",
    ]

    if current_delay is not None:
        summary_parts.append(f"Aktualne opóźnienie: {fmt_delay(current_delay)}")

    summary_parts.append(
        "Czasy przyszłe są szacowane przez dodanie aktualnego opóźnienia do rozkładu."
    )

    st.markdown(
        f'<div class="route-summary">{html.escape(" · ".join(summary_parts))}</div>',
        unsafe_allow_html=True,
    )

    rows: list[str] = []

    for stop in timeline:
        status = stop["status"]
        icon = "✅" if status == "passed" else "🚆" if status == "current" else "○"
        selected_badge = " · wybrana stacja" if stop.get("selected") else ""

        meta_parts: list[str] = []
        if stop.get("platform"):
            meta_parts.append(f'peron {stop["platform"]}')
        if stop.get("track"):
            meta_parts.append(f'tor {stop["track"]}')
        meta_text = " · ".join(meta_parts)

        time_lines: list[str] = []

        if stop["planned_arrival"] is not None:
            time_lines.append(
                f'Plan przyjazd: <strong>{fmt_clock(stop["planned_arrival"])}</strong>'
            )
        if stop["planned_departure"] is not None:
            time_lines.append(
                f'Plan odjazd: <strong>{fmt_clock(stop["planned_departure"])}</strong>'
            )

        if stop["actual_arrival"] is not None:
            delay_text = fmt_delay(stop["arrival_delay"])
            time_lines.append(
                f'Rzeczywisty przyjazd: <strong>{fmt_clock(stop["actual_arrival"])}</strong> '
                f'<span class="{delay_css(stop["arrival_delay"])}">({html.escape(delay_text)})</span>'
            )
        if stop["actual_departure"] is not None:
            delay_text = fmt_delay(stop["departure_delay"])
            time_lines.append(
                f'Rzeczywisty odjazd: <strong>{fmt_clock(stop["actual_departure"])}</strong> '
                f'<span class="{delay_css(stop["departure_delay"])}">({html.escape(delay_text)})</span>'
            )

        if status == "future":
            if stop["estimated_arrival"] is not None:
                time_lines.append(
                    f'<span class="route-estimate">Szacowany przyjazd: '
                    f'{fmt_clock(stop["estimated_arrival"])}</span>'
                )
            if stop["estimated_departure"] is not None:
                time_lines.append(
                    f'<span class="route-estimate">Szacowany odjazd: '
                    f'{fmt_clock(stop["estimated_departure"])}</span>'
                )

        rows.append(
            f'<div class="route-stop {status}">'
            f'<div class="route-icon">{icon}</div>'
            f'<div><div class="route-name">{html.escape(stop["name"])}'
            f'{html.escape(selected_badge)}</div>'
            f'<div class="route-meta">{html.escape(meta_text)}</div></div>'
            f'<div class="route-times">{"<br>".join(time_lines)}</div>'
            f'</div>'
        )

    st.markdown(
        '<div class="route-list">' + "".join(rows) + "</div>",
        unsafe_allow_html=True,
    )


def convert_train(train: dict[str, Any], route: dict[str, Any] | None, station_id: int, operations_map: dict[str, Any], global_map: dict[int, str], dictionaries: dict[str, Any]) -> dict[str, Any] | None:
    point = find_point(train, station_id)
    if point is None:
        return None

    endpoint_name, endpoint_icon, endpoint_css = endpoint_status(point)
    pa, pd = parse_dt(point.get("plannedArrival")), parse_dt(point.get("plannedDeparture"))
    aa, ad = parse_dt(point.get("actualArrival")), parse_dt(point.get("actualDeparture"))

    if endpoint_name == "Stacja początkowa":
        planned_ref, actual_ref, event = pd, ad or pd, "odjazd"
    elif endpoint_name == "Stacja końcowa":
        planned_ref, actual_ref, event = pa, aa or pa, "przyjazd"
    else:
        planned_ref, actual_ref, event = pa or pd, aa or ad or pa or pd, "przyjazd"

    if planned_ref is None or actual_ref is None:
        return None

    schedule_point = find_point(route, station_id) if isinstance(route, dict) else None
    carriers = dictionaries.get("carriers", {})
    categories = dictionaries.get("commercialCategories", {})
    stop_types = dictionaries.get("stopTypes", {})
    carrier_code = str(route.get("carrierCode", "")) if isinstance(route, dict) else ""
    category_symbol = str(route.get("commercialCategorySymbol", "")) if isinstance(route, dict) else ""
    national_number = str(route.get("nationalNumber", "")) if isinstance(route, dict) else ""
    if not national_number:
        national_number = str(train.get("trainOrderId", "—"))
    train_number = " ".join(x for x in (category_symbol, national_number) if x).strip() or "—"

    platform, track, restriction = "—", "", ""
    if isinstance(schedule_point, dict):
        if endpoint_name == "Stacja końcowa":
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
    confirmed_station, confirmed_time = last_confirmed(train, station_id, operations_map, global_map)

    return {
        "schedule_id": train.get("scheduleId"), "order_id": train.get("orderId"), "train_order_id": train.get("trainOrderId"),
        "planned_ref": planned_ref, "actual_ref": actual_ref, "event": event,
        "minutes_until": max(0, int((actual_ref - now()).total_seconds() // 60)),
        "planned_arrival": pa, "planned_departure": pd, "actual_arrival": aa, "actual_departure": ad,
        "arrival_delay": arr_delay, "departure_delay": dep_delay, "reference_delay": reference_delay,
        "relation": relation(train, operations_map, global_map), "train_number": train_number, "train_name": "",
        "carrier": dict_value(carriers, carrier_code, carrier_code or "Przewoźnik nieznany"),
        "category": dict_value(categories, category_symbol, category_symbol), "platform": platform, "track": track,
        "endpoint_name": endpoint_name, "endpoint_icon": endpoint_icon, "endpoint_css": endpoint_css,
        "restriction": restriction, "confirmed": bool(point.get("isConfirmed", False)),
        "last_confirmed_station": confirmed_station, "last_confirmed_time": confirmed_time,
        "_operation_points": [point for point in train.get("stations", []) if isinstance(point, dict)],
        "_schedule_points": [point for point in route.get("stations", []) if isinstance(point, dict)] if isinstance(route, dict) else [],
        "_operations_map": operations_map,
        "_global_map": global_map,
        "_selected_station_id": station_id,
        "route_timeline": [],
        "route_current_delay": None,
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
            details_points = [
                point
                for point in details.get("stations", [])
                if isinstance(point, dict)
            ]
        else:
            details_points = item.get("_schedule_points", [])

        route_timeline, route_current_delay = build_route_timeline(
            item.get("_operation_points", []),
            details_points,
            item.get("_operations_map", {}),
            item.get("_global_map", {}),
            item.get("_selected_station_id", station_id),
        )
        item["route_timeline"] = route_timeline
        item["route_current_delay"] = route_current_delay

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

st.markdown("""
<div class="app-header">
    <div class="signal-stack" aria-hidden="true">
        <span class="signal-dot signal-red"></span>
        <span class="signal-dot signal-amber"></span>
        <span class="signal-dot signal-green"></span>
    </div>
    <div>
        <div class="title">MINI SWDR</div>
        <div class="subtitle">stworzony przez Adriana</div>
    </div>
</div>
<div class="rail-divider"></div>
""", unsafe_allow_html=True)

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

if mode == "live" and not trains:
    st.info("Połączono z API, ale nie znaleziono nadchodzących pociągów.")
elif mode != "live":
    st.error("Nie udało się pobrać danych PKP.")
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
            st.markdown(f'<div class="time">{fmt_clock(train["actual_ref"])}</div>', unsafe_allow_html=True)
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

            pills = []
            if train["endpoint_name"]:
                pills.append(f'<span class="pill {train["endpoint_css"]}">{train["endpoint_icon"]} {html.escape(train["endpoint_name"])}</span>')
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

        expander_title = f'🗺️ Pokaż całą trasę — {train["train_number"]}'
        if train["train_name"]:
            expander_title += f' „{train["train_name"]}”'

        with st.expander(expander_title, expanded=False):
            render_route_timeline(train)

st.caption("Dane: PKP Polskie Linie Kolejowe S.A. • nazwy pociągów pobierane ze szczegółów trasy • przyszłe czasy na trasie są szacowane na podstawie bieżącego opóźnienia")
