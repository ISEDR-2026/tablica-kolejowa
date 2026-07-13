from __future__ import annotations

import html
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from supabase import Client, create_client

st.set_page_config(
    page_title="MINI SWDR",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PROFILE_ID = "adrian"
API = "https://pdp-api.plk-sa.pl/api/v1"
TZ = ZoneInfo("Europe/Warsaw")
TIMEOUT = 30
TRAINS_TTL = 90
STATIONS_TTL = 86400
DETAILS_TTL = 21600
PASS_THROUGH_MAX_SECONDS = 30
TRAIN_LIMITS = [5, 10, 15]

DEFAULT_FAVORITES = [
    "Kamień Pomorski",
    "Wysoka Kamieńska",
    "Gryfice",
    "Goleniów",
]


# ============================================================
# WYGLĄD APLIKACJI
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1180px;
            padding-top: 4.4rem;
            padding-bottom: 2rem;
        }

        .app-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 1rem 1.1rem;
            margin: 0.2rem 0 1.35rem;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-left: 5px solid #ef1b2d;
            border-radius: 14px;
            background:
                linear-gradient(
                    135deg,
                    rgba(22, 29, 40, 0.95),
                    rgba(12, 17, 24, 0.92)
                );
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22);
        }

        .signal-stack {
            display: flex;
            flex-direction: column;
            gap: 0.22rem;
            padding: 0.35rem 0.42rem;
            border-radius: 10px;
            background: #090d12;
            border: 1px solid rgba(255, 255, 255, 0.12);
        }

        .signal-dot {
            width: 0.58rem;
            height: 0.58rem;
            border-radius: 50%;
            display: block;
        }

        .signal-red {
            background: #ef1b2d;
            box-shadow: 0 0 8px rgba(239, 27, 45, 0.65);
        }

        .signal-amber {
            background: #f6c344;
            box-shadow: 0 0 8px rgba(246, 195, 68, 0.45);
        }

        .signal-green {
            background: #42d17d;
            box-shadow: 0 0 8px rgba(66, 209, 125, 0.45);
        }

        .title {
            font-size: 2.3rem;
            font-weight: 850;
            line-height: 1.08;
            letter-spacing: 0.06em;
            margin: 0;
        }

        .subtitle {
            color: #a8adb7;
            font-size: 0.96rem;
            margin-top: 0.28rem;
        }

        .rail-divider {
            height: 4px;
            margin: -0.78rem 0 1.35rem;
            border-radius: 999px;
            background:
                repeating-linear-gradient(
                    90deg,
                    #3c4654 0 26px,
                    #141a22 26px 34px
                );
        }

        .station {
            font-size: 1.4rem;
            font-weight: 750;
            letter-spacing: 0.02em;
        }

        .muted {
            color: #a8adb7;
            font-size: 0.84rem;
        }

        .time {
            font-size: 2rem;
            font-weight: 800;
            line-height: 1;
        }

        .times {
            font-size: 0.9rem;
            margin: 0.3rem 0;
        }

        .train {
            font-size: 1.08rem;
            font-weight: 800;
        }

        .relation {
            font-size: 0.98rem;
            font-weight: 650;
            margin: 0.18rem 0 0.35rem;
        }

        .track {
            display: inline-block;
            margin-top: 0.45rem;
            padding: 0.38rem 0.58rem;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.075);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-left: 3px solid #ef1b2d;
            font-size: 0.88rem;
            font-weight: 750;
            letter-spacing: 0.02em;
        }

        .row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-top: 0.46rem;
        }

        .pill {
            display: inline-block;
            padding: 0.3rem 0.56rem;
            border-radius: 8px;
            font-size: 0.78rem;
            font-weight: 700;
        }

        .stop {
            background: rgba(46, 160, 67, 0.15);
            color: #8ef0a9;
            border: 1px solid rgba(46, 160, 67, 0.28);
        }

        .pass {
            background: rgba(65, 130, 220, 0.17);
            color: #a9d1ff;
            border: 1px solid rgba(65, 130, 220, 0.3);
        }

        .start {
            background: rgba(155, 89, 182, 0.16);
            color: #d8b4f2;
            border: 1px solid rgba(155, 89, 182, 0.3);
        }

        .end {
            background: rgba(230, 126, 34, 0.15);
            color: #ffc58e;
            border: 1px solid rgba(230, 126, 34, 0.3);
        }

        .neutral {
            background: rgba(255, 255, 255, 0.065);
            color: #dce1ea;
            border: 1px solid rgba(255, 255, 255, 0.12);
        }

        .eta-label {
            text-align: right;
            color: #a8adb7;
            font-size: 0.76rem;
        }

        .eta {
            text-align: right;
            font-size: 1.35rem;
            font-weight: 800;
        }

        .status {
            text-align: right;
            margin-top: 0.35rem;
        }

        .status span {
            display: inline-block;
            padding: 0.4rem 0.65rem;
            border-radius: 10px;
            font-size: 0.82rem;
            font-weight: 700;
        }

        .sok {
            background: rgba(46, 160, 67, 0.22);
            color: #8ef0a9;
        }

        .swarn {
            background: rgba(190, 150, 20, 0.22);
            color: #ffd86a;
        }

        .searly {
            background: rgba(65, 130, 220, 0.2);
            color: #9cc8ff;
        }

        .splan {
            background: rgba(255, 255, 255, 0.07);
            color: #dce1ea;
        }

        .note {
            text-align: right;
            color: #a8adb7;
            font-size: 0.74rem;
            margin-top: 0.35rem;
        }

        div[data-testid="stButton"] > button {
            min-height: 2.65rem;
            border-radius: 10px;
            font-weight: 650;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 14px;
        }

        @media (max-width: 640px) {
            .block-container {
                padding-top: 3.8rem;
            }

            .app-header {
                padding: 0.85rem 0.9rem;
            }

            .title {
                font-size: 1.85rem;
            }

            .time {
                font-size: 1.65rem;
            }

            .train {
                font-size: 1rem;
            }

            .eta {
                font-size: 1.1rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CZAS I FORMATOWANIE
# ============================================================

def now() -> datetime:
    return datetime.now(TZ)


def parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ)

    return dt.astimezone(TZ)


def parse_generated(value: Any) -> datetime | None:
    return parse_dt(value)


def norm(value: Any) -> str:
    text = unicodedata.normalize(
        "NFKD",
        str(value or "").strip().lower(),
    )

    return "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(
            float(
                str(value).replace(",", ".")
            )
        )
    except (TypeError, ValueError):
        return default


def dict_value(
    data: Any,
    key: Any,
    default: str = "",
) -> str:
    if not isinstance(data, dict):
        return default

    value = data.get(
        str(key),
        data.get(key),
    )

    if value in (None, ""):
        return default

    return str(value)


def route_key(
    record: dict[str, Any],
) -> tuple[str, str, str]:
    return tuple(
        str(record.get(key, ""))
        for key in (
            "scheduleId",
            "orderId",
            "trainOrderId",
        )
    )


def delay_minutes(
    planned: datetime | None,
    actual: datetime | None,
    api_value: Any,
) -> int | None:
    if api_value not in (None, ""):
        return safe_int(api_value)

    if planned is None or actual is None:
        return None

    return round(
        (
            actual - planned
        ).total_seconds() / 60
    )


def fmt_clock(
    value: datetime | None,
    seconds: bool = False,
) -> str:
    if value is None:
        return "—"

    if seconds:
        return value.strftime("%H:%M:%S")

    return value.strftime("%H:%M")


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

    seconds = max(
        0,
        int(seconds),
    )

    if seconds < 60:
        return f"{seconds} s"

    minutes, remaining_seconds = divmod(
        seconds,
        60,
    )

    if remaining_seconds == 0:
        return f"{minutes} min"

    return (
        f"{minutes} min "
        f"{remaining_seconds} s"
    )


# ============================================================
# SUPABASE
# ============================================================

def supabase_client() -> Client | None:
    try:
        return create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"],
        )
    except Exception as error:
        st.error(
            "Nie udało się połączyć z Supabase."
        )
        st.caption(str(error))
        return None


supabase = supabase_client()


def load_settings() -> tuple[list[str], str]:
    if supabase is None:
        return (
            DEFAULT_FAVORITES.copy(),
            DEFAULT_FAVORITES[0],
        )

    try:
        result = (
            supabase
            .table("train_app_settings")
            .select(
                "favorites, selected_station"
            )
            .eq(
                "profile_id",
                PROFILE_ID,
            )
            .limit(1)
            .execute()
        )

        if result.data:
            row = result.data[0]

            favorites = (
                row.get("favorites")
                or DEFAULT_FAVORITES.copy()
            )

            if isinstance(favorites, list):
                favorites = [
                    str(station)
                    for station in favorites
                    if str(station).strip()
                ]
            else:
                favorites = (
                    DEFAULT_FAVORITES.copy()
                )

            if not favorites:
                favorites = (
                    DEFAULT_FAVORITES.copy()
                )

            selected_station = str(
                row.get("selected_station")
                or favorites[0]
            )

            return (
                favorites,
                selected_station,
            )

    except Exception as error:
        st.warning(
            "Nie udało się odczytać ustawień. "
            "Używam wartości domyślnych."
        )
        st.caption(str(error))

    return (
        DEFAULT_FAVORITES.copy(),
        DEFAULT_FAVORITES[0],
    )


def save_settings() -> bool:
    if supabase is None:
        return False

    try:
        payload = {
            "profile_id": PROFILE_ID,
            "favorites": (
                st.session_state.favorites
            ),
            "selected_station": (
                st.session_state.selected_station
            ),
            "updated_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        }

        (
            supabase
            .table("train_app_settings")
            .upsert(
                payload,
                on_conflict="profile_id",
            )
            .execute()
        )

        st.session_state.settings_error = ""
        return True

    except Exception as error:
        st.session_state.settings_error = (
            str(error)
        )
        return False


# ============================================================
# API PKP PLK
# ============================================================

def headers() -> dict[str, str]:
    return {
        "X-API-Key": str(
            st.secrets["PKP_API_KEY"]
        ).strip(),
        "Accept": "application/json",
    }


def request_api(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> tuple[
    dict[str, Any] | None,
    int,
    str,
]:
    try:
        response = requests.get(
            f"{API}{endpoint}",
            headers=headers(),
            params=params,
            timeout=TIMEOUT,
        )

    except requests.RequestException as error:
        return None, 0, str(error)

    if response.status_code != 200:
        try:
            body = response.json()

            message = (
                body.get("message")
                or body.get("messageEn")
                or body.get("error")
                or response.text
            )

        except ValueError:
            message = response.text

        return (
            None,
            response.status_code,
            str(message)[:600],
        )

    try:
        body = response.json()

    except ValueError:
        return (
            None,
            response.status_code,
            "API zwróciło odpowiedź inną niż JSON.",
        )

    if not isinstance(body, dict):
        return (
            None,
            response.status_code,
            "Nieoczekiwana struktura danych.",
        )

    return (
        body,
        response.status_code,
        "",
    )


@st.cache_data(
    ttl=STATIONS_TTL,
    show_spinner=False,
)
def get_all_stations() -> tuple[
    list[dict[str, Any]],
    int,
    str,
]:
    body, status, error = request_api(
        "/dictionaries/stations",
        {
            "page": 1,
            "pageSize": 10000,
        },
    )

    if body is None:
        return [], status, error

    stations: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()

    for item in body.get("stations", []):
        if not isinstance(item, dict):
            continue

        station_id = safe_int(
            item.get("id"),
            -1,
        )

        station_name = str(
            item.get("name", "")
        ).strip()

        key = (
            station_id,
            norm(station_name),
        )

        if (
            station_id >= 0
            and station_name
            and key not in seen
        ):
            seen.add(key)

            stations.append(
                {
                    "id": station_id,
                    "name": station_name,
                }
            )

    stations.sort(
        key=lambda station: norm(
            station["name"]
        )
    )

    return stations, 200, ""


@st.cache_data(
    ttl=TRAINS_TTL,
    show_spinner=False,
)
def get_operations(
    station_id: int,
) -> tuple[
    dict[str, Any] | None,
    int,
    str,
]:
    return request_api(
        "/operations",
        {
            "stations": station_id,
            "withPlanned": "true",
            "fullRoutes": "true",
            "page": 1,
            "pageSize": 1000,
        },
    )


@st.cache_data(
    ttl=TRAINS_TTL,
    show_spinner=False,
)
def get_schedules(
    station_id: int,
    date_from: str,
    date_to: str,
) -> tuple[
    dict[str, Any] | None,
    int,
    str,
]:
    return request_api(
        "/schedules",
        {
            "stations": station_id,
            "dateFrom": date_from,
            "dateTo": date_to,
            "page": 1,
            "pageSize": 1000,
        },
    )


@st.cache_data(
    ttl=DETAILS_TTL,
    show_spinner=False,
)
def get_route_details(
    schedule_id: Any,
    order_id: Any,
) -> tuple[
    dict[str, Any] | None,
    int,
    str,
]:
    return request_api(
        f"/schedules/route/"
        f"{schedule_id}/"
        f"{order_id}"
    )


# ============================================================
# STACJE I TRASY
# ============================================================

def station_indexes(
    records: list[dict[str, Any]],
) -> tuple[
    dict[str, int],
    dict[int, str],
    list[str],
]:
    name_to_id: dict[str, int] = {}
    id_to_name: dict[int, str] = {}
    names: list[str] = []
    used: set[str] = set()

    for item in records:
        station_id = safe_int(
            item["id"]
        )

        base_name = str(
            item["name"]
        ).strip()

        if base_name not in used:
            display_name = base_name
        else:
            display_name = (
                f"{base_name} "
                f"[{station_id}]"
            )

        used.add(display_name)

        name_to_id[display_name] = (
            station_id
        )

        id_to_name[station_id] = (
            base_name
        )

        names.append(display_name)

    return (
        name_to_id,
        id_to_name,
        names,
    )


def find_point(
    train: dict[str, Any] | None,
    station_id: int,
) -> dict[str, Any] | None:
    if not isinstance(train, dict):
        return None

    for point in train.get(
        "stations",
        [],
    ):
        if not isinstance(point, dict):
            continue

        if (
            safe_int(
                point.get("stationId")
            )
            == station_id
        ):
            return point

    return None


def get_name(
    station_id: int,
    operations_map: dict[str, Any],
    global_map: dict[int, str],
) -> str:
    return dict_value(
        operations_map,
        station_id,
        global_map.get(
            station_id,
            f"Stacja {station_id}",
        ),
    )


def relation(
    train: dict[str, Any],
    operations_map: dict[str, Any],
    global_map: dict[int, str],
) -> str:
    points = [
        point
        for point in train.get(
            "stations",
            [],
        )
        if isinstance(point, dict)
        and point.get("stationId") is not None
    ]

    if not points:
        return "Relacja nieznana"

    first_station_id = safe_int(
        points[0].get("stationId")
    )

    last_station_id = safe_int(
        points[-1].get("stationId")
    )

    first_station_name = get_name(
        first_station_id,
        operations_map,
        global_map,
    )

    last_station_name = get_name(
        last_station_id,
        operations_map,
        global_map,
    )

    return (
        f"{first_station_name}"
        f" → "
        f"{last_station_name}"
    )


# ============================================================
# KLASYFIKACJA RUCHU
# ============================================================

def classify(
    point: dict[str, Any],
) -> tuple[
    str,
    str,
    str,
    int | None,
]:
    planned_arrival = parse_dt(
        point.get("plannedArrival")
    )

    planned_departure = parse_dt(
        point.get("plannedDeparture")
    )

    if (
        planned_arrival is None
        and planned_departure is not None
    ):
        return (
            "Stacja początkowa",
            "🚉",
            "start",
            None,
        )

    if (
        planned_arrival is not None
        and planned_departure is None
    ):
        return (
            "Stacja końcowa",
            "🏁",
            "end",
            None,
        )

    if (
        planned_arrival is not None
        and planned_departure is not None
    ):
        dwell_seconds = max(
            0,
            int(
                (
                    planned_departure
                    - planned_arrival
                ).total_seconds()
            ),
        )

        if (
            dwell_seconds
            <= PASS_THROUGH_MAX_SECONDS
        ):
            return (
                "Przejazd bez postoju",
                "➡️",
                "pass",
                dwell_seconds,
            )

        return (
            "Postój",
            "🛑",
            "stop",
            dwell_seconds,
        )

    return (
        "Punkt trasy",
        "📍",
        "pass",
        None,
    )


def last_confirmed(
    train: dict[str, Any],
    station_id: int,
    operations_map: dict[str, Any],
    global_map: dict[int, str],
) -> tuple[
    str,
    datetime | None,
]:
    points = train.get(
        "stations",
        [],
    )

    selected_index = next(
        (
            index
            for index, point in enumerate(points)
            if isinstance(point, dict)
            and safe_int(
                point.get("stationId")
            ) == station_id
        ),
        len(points) - 1,
    )

    for point in reversed(
        points[: selected_index + 1]
    ):
        if not isinstance(point, dict):
            continue

        if not point.get("isConfirmed"):
            continue

        confirmed_station_id = safe_int(
            point.get("stationId"),
            -1,
        )

        if confirmed_station_id < 0:
            continue

        confirmed_time = (
            parse_dt(
                point.get("actualDeparture")
            )
            or parse_dt(
                point.get("actualArrival")
            )
        )

        confirmed_station_name = get_name(
            confirmed_station_id,
            operations_map,
            global_map,
        )

        return (
            confirmed_station_name,
            confirmed_time,
        )

    return "", None


# ============================================================
# PRZETWARZANIE POCIĄGU
# ============================================================

def convert_train(
    train: dict[str, Any],
    route: dict[str, Any] | None,
    station_id: int,
    operations_map: dict[str, Any],
    global_map: dict[int, str],
    dictionaries: dict[str, Any],
) -> dict[str, Any] | None:
    point = find_point(
        train,
        station_id,
    )

    if point is None:
        return None

    (
        movement,
        movement_icon,
        movement_css,
        planned_dwell,
    ) = classify(point)

    planned_arrival = parse_dt(
        point.get("plannedArrival")
    )

    planned_departure = parse_dt(
        point.get("plannedDeparture")
    )

    actual_arrival = parse_dt(
        point.get("actualArrival")
    )

    actual_departure = parse_dt(
        point.get("actualDeparture")
    )

    if movement == "Stacja początkowa":
        planned_reference = (
            planned_departure
        )

        actual_reference = (
            actual_departure
            or planned_departure
        )

        event_name = "odjazd"

    elif movement == "Stacja końcowa":
        planned_reference = (
            planned_arrival
        )

        actual_reference = (
            actual_arrival
            or planned_arrival
        )

        event_name = "przyjazd"

    elif movement == "Przejazd bez postoju":
        planned_reference = (
            planned_arrival
            or planned_departure
        )

        actual_reference = (
            actual_arrival
            or actual_departure
            or planned_arrival
            or planned_departure
        )

        event_name = "przejazd"

    else:
        planned_reference = (
            planned_arrival
            or planned_departure
        )

        actual_reference = (
            actual_arrival
            or actual_departure
            or planned_arrival
            or planned_departure
        )

        event_name = "przyjazd"

    if (
        planned_reference is None
        or actual_reference is None
    ):
        return None

    schedule_point = find_point(
        route,
        station_id,
    )

    carriers = dictionaries.get(
        "carriers",
        {},
    )

    categories = dictionaries.get(
        "commercialCategories",
        {},
    )

    stop_types = dictionaries.get(
        "stopTypes",
        {},
    )

    carrier_code = ""
    category_symbol = ""
    national_number = ""

    if isinstance(route, dict):
        carrier_code = str(
            route.get("carrierCode", "")
        )

        category_symbol = str(
            route.get(
                "commercialCategorySymbol",
                "",
            )
        )

        national_number = str(
            route.get(
                "nationalNumber",
                "",
            )
        )

    if not national_number:
        national_number = str(
            train.get(
                "trainOrderId",
                "—",
            )
        )

    train_number = " ".join(
        value
        for value in (
            category_symbol,
            national_number,
        )
        if value
    ).strip()

    if not train_number:
        train_number = "—"

    platform = "—"
    track = ""
    restriction = ""

    if isinstance(schedule_point, dict):
        if movement == "Stacja końcowa":
            platform = str(
                schedule_point.get(
                    "arrivalPlatform",
                    schedule_point.get(
                        "departurePlatform",
                        "—",
                    ),
                )
            )

            track = str(
                schedule_point.get(
                    "arrivalTrack",
                    schedule_point.get(
                        "departureTrack",
                        "",
                    ),
                )
            )

        else:
            platform = str(
                schedule_point.get(
                    "departurePlatform",
                    schedule_point.get(
                        "arrivalPlatform",
                        "—",
                    ),
                )
            )

            track = str(
                schedule_point.get(
                    "departureTrack",
                    schedule_point.get(
                        "arrivalTrack",
                        "",
                    ),
                )
            )

        stop_type = (
            schedule_point.get("stopType")
            or schedule_point.get(
                "arrivalStopType"
            )
            or schedule_point.get(
                "departureStopType"
            )
        )

        if stop_type not in (None, ""):
            restriction = dict_value(
                stop_types,
                stop_type,
            )

    arrival_delay = delay_minutes(
        planned_arrival,
        actual_arrival,
        point.get(
            "arrivalDelayMinutes"
        ),
    )

    departure_delay = delay_minutes(
        planned_departure,
        actual_departure,
        point.get(
            "departureDelayMinutes"
        ),
    )

    if event_name == "odjazd":
        reference_delay = departure_delay
    else:
        reference_delay = (
            arrival_delay
            if arrival_delay is not None
            else departure_delay
        )

    actual_dwell = None

    if (
        actual_arrival is not None
        and actual_departure is not None
    ):
        actual_dwell = max(
            0,
            int(
                (
                    actual_departure
                    - actual_arrival
                ).total_seconds()
            ),
        )

    (
        confirmed_station,
        confirmed_time,
    ) = last_confirmed(
        train,
        station_id,
        operations_map,
        global_map,
    )

    minutes_until = max(
        0,
        int(
            (
                actual_reference - now()
            ).total_seconds()
            // 60
        ),
    )

    return {
        "schedule_id": train.get(
            "scheduleId"
        ),
        "order_id": train.get(
            "orderId"
        ),
        "train_order_id": train.get(
            "trainOrderId"
        ),
        "planned_ref": planned_reference,
        "actual_ref": actual_reference,
        "event": event_name,
        "minutes_until": minutes_until,
        "planned_arrival": planned_arrival,
        "planned_departure": planned_departure,
        "actual_arrival": actual_arrival,
        "actual_departure": actual_departure,
        "arrival_delay": arrival_delay,
        "departure_delay": departure_delay,
        "reference_delay": reference_delay,
        "relation": relation(
            train,
            operations_map,
            global_map,
        ),
        "train_number": train_number,
        "train_name": "",
        "carrier": dict_value(
            carriers,
            carrier_code,
            carrier_code
            or "Przewoźnik nieznany",
        ),
        "category": dict_value(
            categories,
            category_symbol,
            category_symbol,
        ),
        "platform": platform,
        "track": track,
        "movement": movement,
        "icon": movement_icon,
        "movement_css": movement_css,
        "planned_dwell": planned_dwell,
        "actual_dwell": actual_dwell,
        "restriction": restriction,
        "confirmed": bool(
            point.get(
                "isConfirmed",
                False,
            )
        ),
        "last_confirmed_station": (
            confirmed_station
        ),
        "last_confirmed_time": (
            confirmed_time
        ),
    }


# ============================================================
# POBIERANIE NAJBLIŻSZYCH POCIĄGÓW
# ============================================================

@st.cache_data(
    ttl=TRAINS_TTL,
    show_spinner=False,
)
def get_live_trains(
    station_id: int,
    global_map: dict[int, str],
    limit: int,
) -> tuple[
    list[dict[str, Any]],
    str,
    int,
    str,
    datetime | None,
]:
    today = now().date()

    (
        operations,
        operations_status,
        operations_error,
    ) = get_operations(station_id)

    if operations is None:
        return (
            [],
            "error",
            operations_status,
            operations_error,
            None,
        )

    (
        schedules,
        schedules_status,
        schedules_error,
    ) = get_schedules(
        station_id,
        today.isoformat(),
        (
            today
            + timedelta(days=1)
        ).isoformat(),
    )

    if schedules is None:
        return (
            [],
            "error",
            schedules_status,
            schedules_error,
            parse_generated(
                operations.get("generatedAt")
            ),
        )

    routes = {
        route_key(route): route
        for route in schedules.get(
            "routes",
            [],
        )
        if isinstance(route, dict)
    }

    dictionaries = schedules.get(
        "dictionaries",
        {},
    )

    if not isinstance(dictionaries, dict):
        dictionaries = {}

    operations_map = operations.get(
        "stations",
        {},
    )

    if not isinstance(operations_map, dict):
        operations_map = {}

    cutoff = (
        now()
        - timedelta(minutes=2)
    )

    converted: list[
        dict[str, Any]
    ] = []

    for item in operations.get(
        "trains",
        [],
    ):
        if not isinstance(item, dict):
            continue

        converted_item = convert_train(
            item,
            routes.get(
                route_key(item)
            ),
            station_id,
            operations_map,
            global_map,
            dictionaries,
        )

        if converted_item is None:
            continue

        if (
            converted_item["actual_ref"]
            < cutoff
        ):
            continue

        converted.append(
            converted_item
        )

    converted.sort(
        key=lambda train: (
            train["actual_ref"]
        )
    )

    unique: list[
        dict[str, Any]
    ] = []

    seen: set[
        tuple[str, str, str]
    ] = set()

    for item in converted:
        unique_key = (
            str(
                item["train_order_id"]
            ),
            item["actual_ref"].strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            item["relation"],
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)
        unique.append(item)

    selected = unique[:limit]

    for item in selected:
        (
            route_details,
            _,
            _,
        ) = get_route_details(
            item["schedule_id"],
            item["order_id"],
        )

        if isinstance(
            route_details,
            dict,
        ):
            item["train_name"] = (
                " ".join(
                    str(
                        route_details.get(
                            "name"
                        )
                        or ""
                    ).split()
                )
            )

    generated_at = parse_generated(
        operations.get("generatedAt")
    )

    return (
        selected,
        "live",
        200,
        "",
        generated_at,
    )


# ============================================================
# POBRANIE LISTY STACJI
# ============================================================

with st.spinner(
    "Pobieram listę stacji PKP PLK…"
):
    (
        station_records,
        stations_status,
        stations_error,
    ) = get_all_stations()


if station_records:
    (
        station_name_to_id,
        station_id_to_name,
        station_names,
    ) = station_indexes(
        station_records
    )

else:
    station_name_to_id = {}
    station_id_to_name = {}
    station_names = (
        DEFAULT_FAVORITES.copy()
    )


# ============================================================
# STAN APLIKACJI
# ============================================================

if "settings_loaded" not in st.session_state:
    (
        favorites,
        selected_station,
    ) = load_settings()

    st.session_state.favorites = (
        favorites
    )

    st.session_state.selected_station = (
        selected_station
    )

    st.session_state.train_limit = 5
    st.session_state.settings_error = ""
    st.session_state.settings_loaded = True


valid_favorites = [
    station
    for station in (
        st.session_state.favorites
    )
    if station in station_names
]

if not valid_favorites:
    valid_favorites = [
        station
        for station in DEFAULT_FAVORITES
        if station in station_names
    ]

if (
    not valid_favorites
    and station_names
):
    valid_favorites = [
        station_names[0]
    ]

st.session_state.favorites = (
    valid_favorites
)


if (
    st.session_state.selected_station
    not in station_names
):
    if st.session_state.favorites:
        st.session_state.selected_station = (
            st.session_state.favorites[0]
        )

    elif station_names:
        st.session_state.selected_station = (
            station_names[0]
        )


if (
    st.session_state.train_limit
    not in TRAIN_LIMITS
):
    st.session_state.train_limit = 5


# ============================================================
# CALLBACKI
# ============================================================

def choose_station(name: str) -> None:
    st.session_state.selected_station = name
    save_settings()


def change_station() -> None:
    choose_station(
        st.session_state.main_station_selector
    )


def add_favorite() -> None:
    name = (
        st.session_state.station_to_add
    )

    if (
        name
        and name
        not in st.session_state.favorites
    ):
        st.session_state.favorites.append(
            name
        )

        save_settings()


def remove_favorite(name: str) -> None:
    if (
        len(
            st.session_state.favorites
        )
        <= 1
    ):
        return

    if (
        name
        in st.session_state.favorites
    ):
        st.session_state.favorites.remove(
            name
        )

    if (
        st.session_state.selected_station
        == name
    ):
        st.session_state.selected_station = (
            st.session_state.favorites[0]
        )

    save_settings()


# ============================================================
# PANEL BOCZNY
# ============================================================

with st.sidebar:
    st.header("⚙️ Ustawienia")

    if supabase is not None:
        st.success(
            "Połączono z Supabase",
            icon="✅",
        )

    if station_records:
        st.success(
            f"Załadowano stacje: "
            f"{len(station_names)}",
            icon="🚉",
        )

    else:
        st.error(
            "Nie udało się pobrać "
            "listy stacji."
        )

        if stations_error:
            st.caption(
                stations_error
            )

    st.subheader("Widok tablicy")

    st.selectbox(
        "Liczba najbliższych pociągów:",
        TRAIN_LIMITS,
        key="train_limit",
    )

    st.subheader("Ulubione stacje")

    available_to_add = [
        station
        for station in station_names
        if station
        not in st.session_state.favorites
    ]

    if available_to_add:
        st.selectbox(
            "Dodaj stację:",
            available_to_add,
            key="station_to_add",
        )

        st.button(
            "➕ Dodaj do ulubionych",
            on_click=add_favorite,
            use_container_width=True,
        )

    for index, station in enumerate(
        st.session_state.favorites.copy()
    ):
        left_column, right_column = (
            st.columns([3, 1])
        )

        with left_column:
            st.write(
                f"⭐ {station}"
            )

        with right_column:
            st.button(
                "✕",
                key=(
                    f"remove_"
                    f"{index}_"
                    f"{station}"
                ),
                on_click=remove_favorite,
                args=(station,),
                disabled=(
                    len(
                        st.session_state.favorites
                    )
                    <= 1
                ),
            )

    st.divider()

    if st.button(
        "🔄 Odśwież dane PKP",
        use_container_width=True,
    ):
        get_live_trains.clear()
        get_operations.clear()
        get_schedules.clear()
        get_route_details.clear()

    if st.button(
        "🔄 Odśwież listę stacji",
        use_container_width=True,
    ):
        get_all_stations.clear()

    st.caption(
        "Dane pociągów są buforowane "
        f"przez {TRAINS_TTL} sekund."
    )

    if st.session_state.settings_error:
        st.error(
            "Nie udało się zapisać ustawień."
        )

        st.caption(
            st.session_state.settings_error
        )


# ============================================================
# NAGŁÓWEK
# ============================================================

st.markdown(
    """
    <div class="app-header">
        <div
            class="signal-stack"
            aria-hidden="true"
        >
            <span
                class="signal-dot signal-red"
            ></span>

            <span
                class="signal-dot signal-amber"
            ></span>

            <span
                class="signal-dot signal-green"
            ></span>
        </div>

        <div>
            <div class="title">
                MINI SWDR
            </div>

            <div class="subtitle">
                stworzony przez Adriana
            </div>
        </div>
    </div>

    <div class="rail-divider"></div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ULUBIONE STACJE
# ============================================================

header_left, header_right = (
    st.columns([3, 1])
)

with header_left:
    st.subheader(
        "⭐ Ulubione stacje"
    )

with header_right:
    st.caption(
        "☰ Edycja w panelu bocznym"
    )


favorite_columns = st.columns(
    min(
        4,
        max(
            1,
            len(
                st.session_state.favorites
            ),
        ),
    )
)


for index, station in enumerate(
    st.session_state.favorites
):
    column = favorite_columns[
        index
        % len(favorite_columns)
    ]

    with column:
        selected = (
            station
            == st.session_state.selected_station
        )

        st.button(
            (
                f"✓ {station}"
                if selected
                else station
            ),
            key=(
                f"favorite_"
                f"{index}_"
                f"{station}"
            ),
            type=(
                "primary"
                if selected
                else "secondary"
            ),
            on_click=choose_station,
            args=(station,),
            use_container_width=True,
        )


# ============================================================
# WYBÓR DOWOLNEJ STACJI
# ============================================================

if station_names:
    if (
        st.session_state.selected_station
        in station_names
    ):
        selected_index = (
            station_names.index(
                st.session_state.selected_station
            )
        )
    else:
        selected_index = 0

    st.selectbox(
        "🔎 Wybierz dowolną stację:",
        station_names,
        index=selected_index,
        key="main_station_selector",
        on_change=change_station,
    )


# ============================================================
# POBRANIE POCIĄGÓW
# ============================================================

selected_station = (
    st.session_state.selected_station
)

selected_station_id = (
    station_name_to_id.get(
        selected_station
    )
)


if selected_station_id is None:
    trains: list[
        dict[str, Any]
    ] = []

    mode = "error"
    status = 404

    error = (
        "Nie znaleziono identyfikatora "
        "wybranej stacji."
    )

    generated = None

else:
    with st.spinner(
        "Pobieram ruch pociągów "
        f"dla stacji "
        f"{selected_station}…"
    ):
        (
            trains,
            mode,
            status,
            error,
            generated,
        ) = get_live_trains(
            selected_station_id,
            station_id_to_name,
            st.session_state.train_limit,
        )


# ============================================================
# KOMUNIKATY API
# ============================================================

if mode == "live" and not trains:
    st.info(
        "Połączono z API, ale nie znaleziono "
        "nadchodzących pociągów."
    )

elif mode != "live":
    st.error(
        "Nie udało się pobrać danych PKP."
    )

    if error:
        st.code(error)


# ============================================================
# NAGŁÓWEK STACJI
# ============================================================

update_time = (
    generated
    or now()
)

with st.container(border=True):
    st.markdown(
        f'<div class="station">'
        f"🚉 {html.escape(selected_station)}"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="muted">'
        f"Ostatnia aktualizacja: "
        f"{update_time:%H:%M:%S}"
        f" · pozycje: {len(trains)}"
        f"</div>",
        unsafe_allow_html=True,
    )


if not trains:
    st.info(
        "Brak nadchodzących pociągów "
        "dla wybranej stacji."
    )


# ============================================================
# KARTY POCIĄGÓW
# ============================================================

for train in trains:
    with st.container(border=True):
        (
            left_column,
            right_column,
        ) = st.columns([3.3, 1])

        with left_column:
            st.markdown(
                f'<div class="time">'
                f'{fmt_clock(train["actual_ref"])}'
                f"</div>",
                unsafe_allow_html=True,
            )

            time_parts: list[str] = []

            if (
                train["planned_arrival"]
                is not None
            ):
                time_parts.append(
                    "Przyjazd "
                    f'{fmt_clock('
                    f'train["planned_arrival"]'
                    f")}"
                    " "
                    f'({fmt_delay('
                    f'train["arrival_delay"]'
                    f")})"
                )

            if (
                train["planned_departure"]
                is not None
            ):
                time_parts.append(
                    "Odjazd "
                    f'{fmt_clock('
                    f'train["planned_departure"]'
                    f")}"
                    " "
                    f'({fmt_delay('
                    f'train["departure_delay"]'
                    f")})"
                )

            if time_parts:
                st.markdown(
                    f'<div class="times">'
                    f'{html.escape('
                    f'" · ".join(time_parts)'
                    f")}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            train_title = (
                train["train_number"]
            )

            if train["train_name"]:
                train_title += (
                    f' · „'
                    f'{train["train_name"]}'
                    f'”'
                )

            st.markdown(
                f'<div class="train">'
                f"{html.escape(train_title)}"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.markdown(
                f'<div class="relation">'
                f'{html.escape('
                f'train["relation"]'
                f")}"
                f"</div>",
                unsafe_allow_html=True,
            )

            details = [
                train["carrier"]
            ]

            if train["category"]:
                details.append(
                    train["category"]
                )

            if train["restriction"]:
                details.append(
                    train["restriction"]
                )

            st.markdown(
                f'<div class="muted">'
                f'{html.escape('
                f'" · ".join(details)'
                f")}"
                f"</div>",
                unsafe_allow_html=True,
            )

            track_parts: list[str] = []

            if (
                train["platform"]
                and train["platform"] != "—"
            ):
                track_parts.append(
                    f'PERON '
                    f'{train["platform"]}'
                )

            if train["track"]:
                track_parts.append(
                    f'TOR '
                    f'{train["track"]}'
                )

            if track_parts:
                st.markdown(
                    f'<div class="track">'
                    f'🚦 '
                    f'{html.escape('
                    f'" · ".join(track_parts)'
                    f")}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            pills: list[str] = [
                (
                    f'<span class="pill '
                    f'{train["movement_css"]}">'
                    f'{train["icon"]} '
                    f'{html.escape('
                    f'train["movement"]'
                    f")}"
                    f"</span>"
                )
            ]

            if (
                train["planned_dwell"]
                is not None
            ):
                pills.append(
                    '<span class="pill neutral">'
                    '⏱️ Postój planowy: '
                    f'{html.escape('
                    f'fmt_duration('
                    f'train["planned_dwell"]'
                    f")"
                    f")}"
                    '</span>'
                )

            if (
                train["actual_dwell"]
                is not None
                and train["movement"]
                == "Postój"
            ):
                pills.append(
                    '<span class="pill neutral">'
                    '📏 Postój rzeczywisty: '
                    f'{html.escape('
                    f'fmt_duration('
                    f'train["actual_dwell"]'
                    f")"
                    f")}"
                    '</span>'
                )

            if train["confirmed"]:
                pills.append(
                    '<span class="pill neutral">'
                    '✅ Dane potwierdzone'
                    '</span>'
                )

            else:
                pills.append(
                    '<span class="pill neutral">'
                    '◌ Dane planowe'
                    '</span>'
                )

            st.markdown(
                '<div class="row">'
                + "".join(pills)
                + "</div>",
                unsafe_allow_html=True,
            )

        with right_column:
            event_name = (
                train["event"].capitalize()
            )

            st.markdown(
                f'<div class="eta-label">'
                f"{html.escape(event_name)}"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.markdown(
                f'<div class="eta">'
                f'za {train["minutes_until"]} min'
                f"</div>",
                unsafe_allow_html=True,
            )

            delay = (
                train["reference_delay"]
            )

            if delay is None:
                status_html = (
                    '<span class="splan">'
                    '◌ Brak danych rzeczywistych'
                    '</span>'
                )

            elif delay == 0:
                status_html = (
                    '<span class="sok">'
                    '✅ Punktualnie'
                    '</span>'
                )

            elif delay > 0:
                status_html = (
                    '<span class="swarn">'
                    f'⚠️ Opóźnienie '
                    f'+{delay} min'
                    '</span>'
                )

            else:
                status_html = (
                    '<span class="searly">'
                    f'ℹ️ Przed czasem '
                    f'{abs(delay)} min'
                    '</span>'
                )

            st.markdown(
                f'<div class="status">'
                f"{status_html}"
                f"</div>",
                unsafe_allow_html=True,
            )

            if train[
                "last_confirmed_station"
            ]:
                confirmed_note = (
                    "Ostatnio potwierdzony:"
                    "<br>"
                    "<strong>"
                    f'{html.escape('
                    f'train['
                    f'"last_confirmed_station"'
                    f"]"
                    f")}"
                    "</strong>"
                )

                if (
                    train[
                        "last_confirmed_time"
                    ]
                    is not None
                ):
                    confirmed_note += (
                        " · "
                        f'{train['
                        f'"last_confirmed_time"'
                        f"]:%H:%M:%S}"
                    )

                st.markdown(
                    f'<div class="note">'
                    f"{confirmed_note}"
                    f"</div>",
                    unsafe_allow_html=True,
                )


# ============================================================
# STOPKA
# ============================================================

st.caption(
    "Dane: PKP Polskie Linie Kolejowe S.A. "
    "• nazwy pociągów pobierane ze szczegółów trasy "
    "• przejazd bez postoju rozpoznawany jako "
    "punkt techniczny do 30 sekund"
)
