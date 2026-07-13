from __future__ import annotations

import hashlib
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from supabase import Client, create_client


# ============================================================
# KONFIGURACJA APLIKACJI
# ============================================================

st.set_page_config(
    page_title="Ruch Pociągów",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PROFILE_ID = "adrian"

PKP_API_BASE_URL = "https://pdp-api.plk-sa.pl/api/v1"
PKP_REQUEST_TIMEOUT = 30
PKP_CACHE_SECONDS = 90

WARSAW_TIMEZONE = ZoneInfo("Europe/Warsaw")

NUMBER_OF_TRAINS = 5

DEFAULT_FAVORITES = [
    "Kamień Pomorski",
    "Wysoka Kamieńska",
    "Gryfice",
    "Goleniów",
]

AVAILABLE_STATIONS = [
    "Goleniów",
    "Gryfice",
    "Kamień Pomorski",
    "Kołobrzeg",
    "Koszalin",
    "Międzyzdroje",
    "Nowogard",
    "Recław",
    "Stargard",
    "Szczecin Dąbie",
    "Szczecin Główny",
    "Szczecin Zdroje",
    "Świnoujście",
    "Świnoujście Centrum",
    "Trzebiatów",
    "Wolin Pomorski",
    "Wysoka Kamieńska",
]


# ============================================================
# STYL APLIKACJI
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1100px;
            padding-top: 2.2rem;
            padding-bottom: 2.2rem;
        }

        .main-title {
            font-size: 2.3rem;
            font-weight: 800;
            margin-top: 0.2rem;
            margin-bottom: 0.15rem;
            line-height: 1.15;
        }

        .subtitle {
            color: #A8ADB7;
            margin-top: 0.15rem;
            margin-bottom: 1.1rem;
            font-size: 1rem;
        }

        .api-banner {
            border-radius: 10px;
            padding: 0.7rem 0.9rem;
            margin-bottom: 1rem;
        }

        .api-live {
            background: rgba(46, 160, 67, 0.14);
            border: 1px solid rgba(46, 160, 67, 0.38);
        }

        .api-warning {
            background: rgba(255, 179, 71, 0.12);
            border: 1px solid rgba(255, 179, 71, 0.35);
        }

        .api-error {
            background: rgba(220, 53, 69, 0.13);
            border: 1px solid rgba(220, 53, 69, 0.35);
        }

        .station-title {
            font-size: 1.45rem;
            font-weight: 750;
            line-height: 1.1;
            margin-bottom: 0.15rem;
        }

        .update-time {
            color: #A8ADB7;
            font-size: 0.88rem;
            line-height: 1.2;
        }

        .train-time {
            font-size: 2.05rem;
            font-weight: 800;
            line-height: 1;
            margin-bottom: 0.35rem;
        }

        .train-direction {
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.15;
            margin-bottom: 0.28rem;
        }

        .train-details {
            color: #A8ADB7;
            font-size: 0.84rem;
            line-height: 1.25;
        }

        .eta-time {
            font-size: 1.45rem;
            font-weight: 800;
            line-height: 1;
            text-align: right;
            margin-bottom: 0.45rem;
        }

        .status-wrap {
            text-align: right;
        }

        .status-pill {
            display: inline-block;
            padding: 0.42rem 0.72rem;
            border-radius: 10px;
            font-size: 0.9rem;
            font-weight: 700;
            line-height: 1.1;
            white-space: nowrap;
        }

        .status-ok {
            background: rgba(46, 160, 67, 0.22);
            color: #8EF0A9;
            border: 1px solid rgba(46, 160, 67, 0.30);
        }

        .status-warn {
            background: rgba(190, 150, 20, 0.22);
            color: #FFD86A;
            border: 1px solid rgba(190, 150, 20, 0.30);
        }

        .status-early {
            background: rgba(65, 130, 220, 0.20);
            color: #9CC8FF;
            border: 1px solid rgba(65, 130, 220, 0.30);
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
                padding-top: 2rem;
                padding-bottom: 1.6rem;
            }

            .main-title {
                font-size: 1.95rem;
            }

            .subtitle {
                font-size: 0.95rem;
                margin-bottom: 0.95rem;
            }

            .station-title {
                font-size: 1.25rem;
            }

            .train-time {
                font-size: 1.7rem;
                margin-bottom: 0.28rem;
            }

            .train-direction {
                font-size: 0.98rem;
                margin-bottom: 0.22rem;
            }

            .train-details {
                font-size: 0.8rem;
            }

            .eta-time {
                font-size: 1.2rem;
                margin-bottom: 0.35rem;
            }

            .status-pill {
                padding: 0.36rem 0.6rem;
                font-size: 0.82rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CZAS
# ============================================================

def now_warsaw() -> datetime:
    return datetime.now(WARSAW_TIMEZONE)


def today_warsaw() -> date:
    return now_warsaw().date()


def parse_local_datetime(value: Any) -> datetime | None:
    """
    Czasy przejazdów zwracane przez API mają postać lokalną,
    np. 2026-07-13T06:21:00, bez oznaczenia strefy.
    Interpretujemy je jako Europe/Warsaw.
    """

    if value in (None, ""):
        return None

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=WARSAW_TIMEZONE)

    return parsed.astimezone(WARSAW_TIMEZONE)


def parse_generated_at(value: Any) -> datetime | None:
    """
    generatedAt kończy się literą Z, czyli jest podany w UTC.
    """

    if value in (None, ""):
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(WARSAW_TIMEZONE)


# ============================================================
# FUNKCJE POMOCNICZE
# ============================================================

def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", text)

    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def dictionary_value(
    dictionary: Any,
    key: Any,
    default: str,
) -> str:
    if not isinstance(dictionary, dict):
        return default

    key_text = str(key)

    value = dictionary.get(key_text)

    if value in (None, ""):
        value = dictionary.get(key)

    return str(value) if value not in (None, "") else default


def route_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("scheduleId", "")),
        str(record.get("orderId", "")),
        str(record.get("trainOrderId", "")),
    )


def station_name_from_map(
    station_map: dict[str, Any],
    station_id: Any,
) -> str:
    return dictionary_value(
        station_map,
        station_id,
        f"Stacja {station_id}",
    )


def calculate_delay_minutes(
    planned_time: datetime | None,
    actual_time: datetime | None,
    api_delay: Any = None,
) -> int:
    if api_delay not in (None, ""):
        return safe_int(api_delay, 0)

    if planned_time is None or actual_time is None:
        return 0

    difference = actual_time - planned_time

    return int(round(difference.total_seconds() / 60))


# ============================================================
# SUPABASE
# ============================================================

def get_supabase_client() -> Client | None:
    try:
        return create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"],
        )

    except Exception as error:
        st.error("Nie udało się połączyć z Supabase.")
        st.caption(str(error))
        return None


supabase = get_supabase_client()


def load_settings() -> tuple[list[str], str]:
    if supabase is None:
        return (
            DEFAULT_FAVORITES.copy(),
            DEFAULT_FAVORITES[0],
        )

    try:
        response = (
            supabase
            .table("train_app_settings")
            .select("favorites, selected_station")
            .eq("profile_id", PROFILE_ID)
            .limit(1)
            .execute()
        )

        if response.data:
            row = response.data[0]

            favorites = row.get(
                "favorites",
                DEFAULT_FAVORITES.copy(),
            )

            selected_station = row.get(
                "selected_station",
                DEFAULT_FAVORITES[0],
            )

            valid_favorites = [
                station
                for station in favorites
                if station in AVAILABLE_STATIONS
            ]

            if not valid_favorites:
                valid_favorites = DEFAULT_FAVORITES.copy()

            if selected_station not in AVAILABLE_STATIONS:
                selected_station = valid_favorites[0]

            return valid_favorites, selected_station

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
            "favorites": st.session_state.favorites,
            "selected_station": (
                st.session_state.selected_station
            ),
            "updated_at": datetime.now(timezone.utc).isoformat(),
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

        st.session_state.settings_saved = True
        st.session_state.settings_error = ""

        return True

    except Exception as error:
        st.session_state.settings_error = str(error)
        return False


# ============================================================
# STAN APLIKACJI
# ============================================================

if "settings_loaded" not in st.session_state:
    loaded_favorites, loaded_station = load_settings()

    st.session_state.favorites = loaded_favorites
    st.session_state.selected_station = loaded_station
    st.session_state.settings_loaded = True
    st.session_state.settings_saved = False
    st.session_state.settings_error = ""


# ============================================================
# CALLBACKI
# ============================================================

def choose_station(station: str) -> None:
    st.session_state.selected_station = station
    save_settings()


def handle_station_select() -> None:
    choose_station(
        st.session_state.main_station_selector
    )


def add_favorite() -> None:
    station = st.session_state.station_to_add

    if (
        station
        and station not in st.session_state.favorites
    ):
        st.session_state.favorites.append(station)
        save_settings()


def remove_favorite(station: str) -> None:
    if len(st.session_state.favorites) <= 1:
        return

    if station in st.session_state.favorites:
        st.session_state.favorites.remove(station)

    if st.session_state.selected_station == station:
        st.session_state.selected_station = (
            st.session_state.favorites[0]
        )

    save_settings()


# ============================================================
# API PKP PLK
# ============================================================

def get_pkp_headers() -> dict[str, str]:
    return {
        "X-API-Key": str(st.secrets["PKP_API_KEY"]).strip(),
        "Accept": "application/json",
    }


def pkp_request(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, int, str]:
    try:
        response = requests.get(
            f"{PKP_API_BASE_URL}{endpoint}",
            headers=get_pkp_headers(),
            params=params,
            timeout=PKP_REQUEST_TIMEOUT,
        )

    except requests.RequestException as error:
        return None, 0, str(error)

    if response.status_code != 200:
        try:
            payload = response.json()

            message = (
                payload.get("message")
                or payload.get("messageEn")
                or payload.get("error")
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
        payload = response.json()
    except ValueError:
        return (
            None,
            response.status_code,
            "API zwróciło odpowiedź, która nie jest JSON-em.",
        )

    if not isinstance(payload, dict):
        return (
            None,
            response.status_code,
            "API zwróciło nieoczekiwaną strukturę danych.",
        )

    return payload, response.status_code, ""


@st.cache_data(ttl=86400, show_spinner=False)
def get_station_id(
    station_name: str,
) -> tuple[int | None, int, str]:
    payload, status_code, error_message = pkp_request(
        "/dictionaries/stations",
        params={
            "search": station_name,
            "page": 1,
            "pageSize": 50,
        },
    )

    if payload is None:
        return None, status_code, error_message

    stations = payload.get("stations", [])

    if not isinstance(stations, list):
        return (
            None,
            500,
            "API nie zwróciło listy stations.",
        )

    normalized_target = normalize_text(station_name)
    partial_match: int | None = None

    for station in stations:
        if not isinstance(station, dict):
            continue

        station_id = station.get("id")
        returned_name = station.get("name")

        if station_id is None or returned_name is None:
            continue

        normalized_returned = normalize_text(returned_name)

        if normalized_returned == normalized_target:
            return safe_int(station_id), 200, ""

        if (
            normalized_target in normalized_returned
            or normalized_returned in normalized_target
        ):
            partial_match = safe_int(station_id)

    if partial_match is not None:
        return partial_match, 200, ""

    return (
        None,
        404,
        f"Nie znaleziono stacji: {station_name}",
    )


@st.cache_data(
    ttl=PKP_CACHE_SECONDS,
    show_spinner=False,
)
def get_operations(
    station_id: int,
) -> tuple[dict[str, Any] | None, int, str]:
    return pkp_request(
        "/operations",
        params={
            "stations": station_id,
            "withPlanned": "true",
            "fullRoutes": "true",
            "page": 1,
            "pageSize": 1000,
        },
    )


@st.cache_data(
    ttl=PKP_CACHE_SECONDS,
    show_spinner=False,
)
def get_schedules(
    station_id: int,
    date_from: str,
    date_to: str,
) -> tuple[dict[str, Any] | None, int, str]:
    return pkp_request(
        "/schedules",
        params={
            "stations": station_id,
            "dateFrom": date_from,
            "dateTo": date_to,
            "page": 1,
            "pageSize": 1000,
        },
    )


# ============================================================
# ŁĄCZENIE OPERATIONS + SCHEDULES
# ============================================================

def build_schedule_map(
    schedules_payload: dict[str, Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    routes = schedules_payload.get("routes", [])

    if not isinstance(routes, list):
        return {}

    result: dict[
        tuple[str, str, str],
        dict[str, Any],
    ] = {}

    for route in routes:
        if not isinstance(route, dict):
            continue

        result[route_key(route)] = route

    return result


def find_station_event(
    train: dict[str, Any],
    station_id: int,
) -> dict[str, Any] | None:
    stations = train.get("stations", [])

    if not isinstance(stations, list):
        return None

    for station in stations:
        if not isinstance(station, dict):
            continue

        if safe_int(station.get("stationId")) == station_id:
            return station

    return None


def find_schedule_station(
    route: dict[str, Any] | None,
    station_id: int,
) -> dict[str, Any] | None:
    if not isinstance(route, dict):
        return None

    stations = route.get("stations", [])

    if not isinstance(stations, list):
        return None

    for station in stations:
        if not isinstance(station, dict):
            continue

        if safe_int(station.get("stationId")) == station_id:
            return station

    return None


def get_train_direction(
    train: dict[str, Any],
    station_id: int,
    station_map: dict[str, Any],
) -> tuple[str, str]:
    stations = train.get("stations", [])

    if not isinstance(stations, list) or not stations:
        return "Kierunek nieznany", "→"

    valid_stations = [
        station
        for station in stations
        if isinstance(station, dict)
        and station.get("stationId") is not None
    ]

    if not valid_stations:
        return "Kierunek nieznany", "→"

    first_station_id = valid_stations[0].get("stationId")
    last_station_id = valid_stations[-1].get("stationId")

    first_name = station_name_from_map(
        station_map,
        first_station_id,
    )

    last_name = station_name_from_map(
        station_map,
        last_station_id,
    )

    if safe_int(last_station_id) == station_id:
        return f"z {first_name}", "←"

    return last_name, "→"


def select_event_times(
    station_event: dict[str, Any],
) -> tuple[
    datetime | None,
    datetime | None,
    str,
]:
    planned_departure = parse_local_datetime(
        station_event.get("plannedDeparture")
    )

    actual_departure = parse_local_datetime(
        station_event.get("actualDeparture")
    )

    planned_arrival = parse_local_datetime(
        station_event.get("plannedArrival")
    )

    actual_arrival = parse_local_datetime(
        station_event.get("actualArrival")
    )

    if planned_departure is not None:
        return (
            planned_departure,
            actual_departure or planned_departure,
            "odjazd",
        )

    if planned_arrival is not None:
        return (
            planned_arrival,
            actual_arrival or planned_arrival,
            "przyjazd",
        )

    return None, None, "przejazd"


def convert_train_record(
    operation_train: dict[str, Any],
    schedule_route: dict[str, Any] | None,
    selected_station_id: int,
    operation_station_map: dict[str, Any],
    schedule_dictionaries: dict[str, Any],
) -> dict[str, Any] | None:
    station_event = find_station_event(
        operation_train,
        selected_station_id,
    )

    if station_event is None:
        return None

    planned_time, actual_time, event_type = (
        select_event_times(station_event)
    )

    if planned_time is None or actual_time is None:
        return None

    schedule_station = find_schedule_station(
        schedule_route,
        selected_station_id,
    )

    carriers = schedule_dictionaries.get(
        "carriers",
        {},
    )

    categories = schedule_dictionaries.get(
        "commercialCategories",
        {},
    )

    carrier_code = ""

    if isinstance(schedule_route, dict):
        carrier_code = str(
            schedule_route.get("carrierCode", "")
        )

    carrier_name = dictionary_value(
        carriers,
        carrier_code,
        carrier_code or "Przewoźnik nieznany",
    )

    category_symbol = ""

    if isinstance(schedule_route, dict):
        category_symbol = str(
            schedule_route.get(
                "commercialCategorySymbol",
                "",
            )
        )

    category_name = dictionary_value(
        categories,
        category_symbol,
        category_symbol,
    )

    national_number = ""

    if isinstance(schedule_route, dict):
        national_number = str(
            schedule_route.get("nationalNumber", "")
        )

    if not national_number:
        national_number = str(
            operation_train.get("trainOrderId", "—")
        )

    train_label = " ".join(
        part
        for part in [
            category_symbol,
            national_number,
        ]
        if part
    ).strip()

    if not train_label:
        train_label = national_number or "—"

    platform = "—"
    track = ""

    if isinstance(schedule_station, dict):
        if event_type == "przyjazd":
            platform = str(
                schedule_station.get(
                    "arrivalPlatform",
                    schedule_station.get(
                        "departurePlatform",
                        "—",
                    ),
                )
            )

            track = str(
                schedule_station.get(
                    "arrivalTrack",
                    schedule_station.get(
                        "departureTrack",
                        "",
                    ),
                )
            )
        else:
            platform = str(
                schedule_station.get(
                    "departurePlatform",
                    schedule_station.get(
                        "arrivalPlatform",
                        "—",
                    ),
                )
            )

            track = str(
                schedule_station.get(
                    "departureTrack",
                    schedule_station.get(
                        "arrivalTrack",
                        "",
                    ),
                )
            )

    if event_type == "przyjazd":
        api_delay = station_event.get(
            "arrivalDelayMinutes"
        )
    else:
        api_delay = station_event.get(
            "departureDelayMinutes"
        )

    delay_minutes = calculate_delay_minutes(
        planned_time,
        actual_time,
        api_delay,
    )

    direction, direction_symbol = get_train_direction(
        operation_train,
        selected_station_id,
        operation_station_map,
    )

    minutes_until = int(
        (actual_time - now_warsaw()).total_seconds()
        // 60
    )

    return {
        "schedule_id": operation_train.get(
            "scheduleId"
        ),
        "order_id": operation_train.get("orderId"),
        "train_order_id": operation_train.get(
            "trainOrderId"
        ),
        "planned_time": planned_time,
        "actual_time": actual_time,
        "minutes_until": max(0, minutes_until),
        "direction": direction,
        "direction_symbol": direction_symbol,
        "train_number": train_label,
        "carrier": carrier_name,
        "carrier_code": carrier_code,
        "category": category_name,
        "category_symbol": category_symbol,
        "platform": platform,
        "track": track,
        "delay": delay_minutes,
        "event_type": event_type,
        "confirmed": bool(
            station_event.get("isConfirmed", False)
        ),
    }


@st.cache_data(
    ttl=PKP_CACHE_SECONDS,
    show_spinner=False,
)
def get_live_trains(
    station_name: str,
) -> tuple[
    list[dict[str, Any]],
    str,
    int,
    str,
    datetime | None,
]:
    station_id, status_code, error_message = (
        get_station_id(station_name)
    )

    if station_id is None:
        return (
            [],
            "error",
            status_code,
            error_message,
            None,
        )

    local_today = today_warsaw()
    local_tomorrow = local_today + timedelta(days=1)

    operations_payload, operations_status, operations_error = (
        get_operations(station_id)
    )

    if operations_payload is None:
        return (
            [],
            "error",
            operations_status,
            operations_error,
            None,
        )

    schedules_payload, schedules_status, schedules_error = (
        get_schedules(
            station_id,
            local_today.isoformat(),
            local_tomorrow.isoformat(),
        )
    )

    if schedules_payload is None:
        return (
            [],
            "error",
            schedules_status,
            schedules_error,
            parse_generated_at(
                operations_payload.get("generatedAt")
            ),
        )

    operation_trains = operations_payload.get(
        "trains",
        [],
    )

    if not isinstance(operation_trains, list):
        return (
            [],
            "error",
            500,
            "API operations nie zwróciło pola trains.",
            None,
        )

    operation_station_map = operations_payload.get(
        "stations",
        {},
    )

    if not isinstance(operation_station_map, dict):
        operation_station_map = {}

    schedule_map = build_schedule_map(
        schedules_payload
    )

    dictionaries = schedules_payload.get(
        "dictionaries",
        {},
    )

    if not isinstance(dictionaries, dict):
        dictionaries = {}

    converted: list[dict[str, Any]] = []

    oldest_allowed = now_warsaw() - timedelta(
        minutes=2
    )

    for operation_train in operation_trains:
        if not isinstance(operation_train, dict):
            continue

        schedule_route = schedule_map.get(
            route_key(operation_train)
        )

        train = convert_train_record(
            operation_train,
            schedule_route,
            station_id,
            operation_station_map,
            dictionaries,
        )

        if train is None:
            continue

        if train["actual_time"] < oldest_allowed:
            continue

        converted.append(train)

    converted.sort(
        key=lambda train: train["actual_time"]
    )

    unique_trains: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for train in converted:
        unique_key = (
            str(train["train_order_id"]),
            train["actual_time"].strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            train["direction"],
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)
        unique_trains.append(train)

    generated_at = parse_generated_at(
        operations_payload.get("generatedAt")
    )

    return (
        unique_trains[:NUMBER_OF_TRAINS],
        "live",
        200,
        "",
        generated_at,
    )


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
    else:
        st.error(
            "Brak połączenia z Supabase",
            icon="⚠️",
        )

    st.subheader("Ulubione stacje")

    stations_to_add = [
        station
        for station in AVAILABLE_STATIONS
        if station not in st.session_state.favorites
    ]

    if stations_to_add:
        st.selectbox(
            "Dodaj stację:",
            options=stations_to_add,
            key="station_to_add",
        )

        st.button(
            "➕ Dodaj do ulubionych",
            on_click=add_favorite,
            use_container_width=True,
        )
    else:
        st.info(
            "Wszystkie dostępne stacje są już dodane."
        )

    st.divider()

    for index, station in enumerate(
        st.session_state.favorites.copy()
    ):
        left, right = st.columns([3, 1])

        with left:
            st.write(f"⭐ {station}")

        with right:
            st.button(
                "✕",
                key=f"remove_{index}_{station}",
                on_click=remove_favorite,
                args=(station,),
                disabled=(
                    len(
                        st.session_state.favorites
                    ) <= 1
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
        get_station_id.clear()

    st.caption(
        f"Dane API są buforowane przez "
        f"{PKP_CACHE_SECONDS} sekund."
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
    '<div class="main-title">'
    "🚆 Ruch Pociągów"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "Pięć najbliższych pociągów "
    "dla wybranej stacji"
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# ULUBIONE STACJE
# ============================================================

header_left, header_right = st.columns([3, 1])

with header_left:
    st.subheader("⭐ Ulubione stacje")

with header_right:
    st.caption(
        "☰ Edycja w panelu bocznym"
    )


favorites = st.session_state.favorites

favorite_columns = st.columns(
    min(
        4,
        max(1, len(favorites)),
    )
)

for index, station in enumerate(favorites):
    column = favorite_columns[
        index % len(favorite_columns)
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
            key=f"favorite_{index}_{station}",
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
# WYBÓR STACJI
# ============================================================

if (
    st.session_state.selected_station
    in AVAILABLE_STATIONS
):
    selected_index = AVAILABLE_STATIONS.index(
        st.session_state.selected_station
    )
else:
    selected_index = 0


st.selectbox(
    "🔎 Wybierz inną stację:",
    options=AVAILABLE_STATIONS,
    index=selected_index,
    key="main_station_selector",
    on_change=handle_station_select,
)


# ============================================================
# POBRANIE PRAWDZIWYCH DANYCH
# ============================================================

selected_station = (
    st.session_state.selected_station
)

with st.spinner(
    f"Pobieram ruch pociągów dla stacji "
    f"{selected_station}…"
):
    (
        trains,
        api_mode,
        api_status,
        api_error,
        api_generated_at,
    ) = get_live_trains(selected_station)


# ============================================================
# STATUS API
# ============================================================

if api_mode == "live" and trains:
    st.markdown(
        """
        <div class="api-banner api-live">
            ✅ <strong>Dane rzeczywiste PKP PLK</strong>
            — wyświetlane są najbliższe pociągi.
        </div>
        """,
        unsafe_allow_html=True,
    )

elif api_mode == "live" and not trains:
    st.markdown(
        """
        <div class="api-banner api-warning">
            ℹ️ Połączono z API PKP PLK, ale obecnie
            nie znaleziono nadchodzących pociągów
            dla wybranej stacji.
        </div>
        """,
        unsafe_allow_html=True,
    )

elif api_status in (401, 403):
    st.markdown(
        """
        <div class="api-banner api-error">
            🔐 <strong>API odrzuciło klucz.</strong>
            Sprawdź wartość PKP_API_KEY w Secrets.
        </div>
        """,
        unsafe_allow_html=True,
    )

elif api_status == 429:
    st.markdown(
        """
        <div class="api-banner api-warning">
            ⏳ Osiągnięto chwilowy limit zapytań API.
            Spróbuj ponownie za kilka minut.
        </div>
        """,
        unsafe_allow_html=True,
    )

else:
    st.markdown(
        """
        <div class="api-banner api-error">
            ⚠️ <strong>Nie udało się pobrać danych PKP.</strong>
            Szczegóły znajdziesz poniżej.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if api_error:
        st.code(api_error)


# ============================================================
# NAGŁÓWEK WYBRANEJ STACJI
# ============================================================

display_update_time = (
    api_generated_at
    if api_generated_at is not None
    else now_warsaw()
)

with st.container(border=True):
    st.markdown(
        f'<div class="station-title">'
        f"🚉 {selected_station}"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="update-time">'
        f"Ostatnia aktualizacja danych: "
        f"{display_update_time:%H:%M:%S}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# KARTY POCIĄGÓW
# ============================================================

if not trains:
    st.info(
        "Brak nadchodzących pociągów "
        "dla wybranej stacji."
    )


for train in trains:
    with st.container(border=True):
        left_column, right_column = st.columns(
            [3, 1]
        )

        with left_column:
            st.markdown(
                f'<div class="train-time">'
                f"{train['actual_time']:%H:%M}"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.markdown(
                f'<div class="train-direction">'
                f"{train['direction_symbol']} "
                f"{train['direction']}"
                f"</div>",
                unsafe_allow_html=True,
            )

            details_parts = [
                str(train["train_number"]),
                str(train["carrier"]),
            ]

            if (
                train["platform"]
                and train["platform"] != "—"
            ):
                details_parts.append(
                    f"peron {train['platform']}"
                )

            if train["track"]:
                details_parts.append(
                    f"tor {train['track']}"
                )

            details_parts.append(
                train["event_type"]
            )

            if train["delay"] != 0:
                details_parts.append(
                    "planowo "
                    f"{train['planned_time']:%H:%M}"
                )

            details = " · ".join(details_parts)

            st.markdown(
                f'<div class="train-details">'
                f"{details}"
                f"</div>",
                unsafe_allow_html=True,
            )

        with right_column:
            st.markdown(
                f'<div class="eta-time">'
                f"za {train['minutes_until']} min"
                f"</div>",
                unsafe_allow_html=True,
            )

            if train["delay"] == 0:
                status_html = (
                    '<div class="status-wrap">'
                    '<span class="status-pill status-ok">'
                    '✅ Punktualnie'
                    '</span></div>'
                )

            elif train["delay"] > 0:
                status_html = (
                    '<div class="status-wrap">'
                    '<span class="status-pill status-warn">'
                    f'⚠️ Opóźnienie '
                    f'+{train["delay"]} min'
                    '</span></div>'
                )

            else:
                status_html = (
                    '<div class="status-wrap">'
                    '<span class="status-pill status-early">'
                    f'ℹ️ Przed czasem '
                    f'{abs(train["delay"])} min'
                    '</span></div>'
                )

            st.markdown(
                status_html,
                unsafe_allow_html=True,
            )


st.caption(
    "Dane rzeczywiste: PKP Polskie Linie Kolejowe S.A. "
    "• ustawienia zapisane w Supabase"
)
