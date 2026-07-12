from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
import streamlit as st
from supabase import Client, create_client


# ============================================================
# KONFIGURACJA
# ============================================================

st.set_page_config(
    page_title="Ruch Pociągów",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PROFILE_ID = "adrian"

PKP_API_BASE_URL = "https://pdp-api.plk-sa.pl/api/v1"
PKP_REQUEST_TIMEOUT = 20

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

NUMBER_OF_TRAINS = 5


# ============================================================
# STYL
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

        .api-test {
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
            line-height: 1.2;
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

        .status-cancelled {
            background: rgba(220, 53, 69, 0.22);
            color: #FF9AA8;
            border: 1px solid rgba(220, 53, 69, 0.30);
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
# FUNKCJE POMOCNICZE
# ============================================================

def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)

    return "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )


def first_value(
    record: dict[str, Any],
    names: list[str],
    default: Any = None,
) -> Any:
    normalized_record = {
        normalize_text(key).replace("_", "").replace("-", ""): value
        for key, value in record.items()
    }

    for name in names:
        normalized_name = (
            normalize_text(name)
            .replace("_", "")
            .replace("-", "")
        )

        if normalized_name in normalized_record:
            value = normalized_record[normalized_name]

            if value not in (None, ""):
                return value

    return default


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [
            item
            for item in payload
            if isinstance(item, dict)
        ]

    if not isinstance(payload, dict):
        return []

    preferred_keys = [
        "data",
        "items",
        "results",
        "records",
        "operations",
        "schedules",
        "stations",
        "value",
    ]

    for key in preferred_keys:
        value = payload.get(key)

        if isinstance(value, list):
            return [
                item
                for item in value
                if isinstance(item, dict)
            ]

        if isinstance(value, dict):
            nested = extract_records(value)

            if nested:
                return nested

    for value in payload.values():
        if isinstance(value, list):
            records = [
                item
                for item in value
                if isinstance(item, dict)
            ]

            if records:
                return records

        if isinstance(value, dict):
            nested = extract_records(value)

            if nested:
                return nested

    return []


def parse_datetime_value(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        result = value
    else:
        text = str(value).strip()

        if not text:
            return None

        text = text.replace("Z", "+00:00")

        result = None

        formats = [
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%H:%M:%S",
            "%H:%M",
        ]

        try:
            result = datetime.fromisoformat(text)
        except ValueError:
            for date_format in formats:
                try:
                    parsed = datetime.strptime(
                        text,
                        date_format,
                    )

                    if parsed.year == 1900:
                        now = datetime.now()
                        parsed = parsed.replace(
                            year=now.year,
                            month=now.month,
                            day=now.day,
                        )

                    result = parsed
                    break

                except ValueError:
                    continue

        if result is None:
            time_match = re.search(
                r"\b([01]?\d|2[0-3]):([0-5]\d)\b",
                text,
            )

            if time_match:
                now = datetime.now()

                result = now.replace(
                    hour=int(time_match.group(1)),
                    minute=int(time_match.group(2)),
                    second=0,
                    microsecond=0,
                )

    if result.tzinfo is not None:
        result = result.astimezone().replace(
            tzinfo=None
        )

    return result


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


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
        st.error(
            "Nie udało się połączyć z Supabase."
        )
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
                valid_favorites = (
                    DEFAULT_FAVORITES.copy()
                )

            if selected_station not in AVAILABLE_STATIONS:
                selected_station = valid_favorites[0]

            return valid_favorites, selected_station

    except Exception as error:
        st.warning(
            "Nie udało się odczytać ustawień."
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
            "updated_at": (
                datetime.now(timezone.utc).isoformat()
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

        st.session_state.settings_saved = True
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


def handle_station_select() -> None:
    choose_station(
        st.session_state.main_station_selector
    )


# ============================================================
# API PKP PLK
# ============================================================

def get_pkp_headers() -> dict[str, str]:
    return {
        "X-API-Key": st.secrets["PKP_API_KEY"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def pkp_request(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> tuple[Any | None, int, str]:
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
            error_payload = response.json()
            message = (
                error_payload.get("message")
                or error_payload.get("error")
                or response.text
            )
        except ValueError:
            message = response.text

        return (
            None,
            response.status_code,
            str(message)[:500],
        )

    try:
        return response.json(), 200, ""

    except ValueError:
        return (
            None,
            response.status_code,
            "API zwróciło nieprawidłowy JSON.",
        )


@st.cache_data(ttl=86400, show_spinner=False)
def get_station_id(
    station_name: str,
) -> tuple[str | None, int, str]:
    payload, status_code, error_message = (
        pkp_request(
            "/dictionaries/stations",
            params={
                "search": station_name,
                "page": 1,
                "pageSize": 50,
            },
        )
    )

    if status_code != 200:
        return None, status_code, error_message

    records = extract_records(payload)

    normalized_target = normalize_text(station_name)

    best_station_id = None

    for record in records:
        name = first_value(
            record,
            [
                "name",
                "stationName",
                "station",
                "nazwa",
                "nazwaStacji",
            ],
        )

        station_id = first_value(
            record,
            [
                "id",
                "stationId",
                "stationCode",
                "code",
                "identyfikator",
            ],
        )

        if station_id is None:
            continue

        normalized_name = normalize_text(name)

        if normalized_name == normalized_target:
            return str(station_id), 200, ""

        if (
            normalized_target in normalized_name
            or normalized_name in normalized_target
        ):
            best_station_id = str(station_id)

    if best_station_id is not None:
        return best_station_id, 200, ""

    return (
        None,
        404,
        f"Nie znaleziono ID stacji: {station_name}",
    )


def operation_to_train(
    record: dict[str, Any],
    selected_station: str,
) -> dict[str, Any] | None:
    nested_station = first_value(
        record,
        [
            "station",
            "stationData",
            "location",
            "point",
        ],
        {},
    )

    if isinstance(nested_station, dict):
        merged_record = {
            **record,
            **{
                f"nested_{key}": value
                for key, value in nested_station.items()
            },
        }
    else:
        merged_record = record

    station_name = first_value(
        merged_record,
        [
            "stationName",
            "name",
            "nazwaStacji",
            "nested_name",
            "nested_stationName",
        ],
        selected_station,
    )

    planned_time = parse_datetime_value(
        first_value(
            merged_record,
            [
                "plannedDeparture",
                "plannedDepartureTime",
                "plannedArrival",
                "plannedArrivalTime",
                "plannedTime",
                "scheduledTime",
                "timetableTime",
                "departureTimePlanned",
                "arrivalTimePlanned",
            ],
        )
    )

    actual_time = parse_datetime_value(
        first_value(
            merged_record,
            [
                "estimatedDeparture",
                "estimatedDepartureTime",
                "actualDeparture",
                "actualDepartureTime",
                "estimatedArrival",
                "estimatedArrivalTime",
                "actualArrival",
                "actualArrivalTime",
                "currentTime",
                "realTime",
            ],
        )
    )

    delay = safe_int(
        first_value(
            merged_record,
            [
                "delay",
                "delayMinutes",
                "departureDelay",
                "arrivalDelay",
                "calculatedDelay",
            ],
            0,
        ),
        0,
    )

    if actual_time is None and planned_time is not None:
        actual_time = (
            planned_time
            + timedelta(minutes=delay)
        )

    if planned_time is None and actual_time is not None:
        planned_time = (
            actual_time
            - timedelta(minutes=delay)
        )

    if actual_time is None:
        return None

    destination = first_value(
        merged_record,
        [
            "destination",
            "destinationName",
            "finalStation",
            "finalStationName",
            "toStation",
            "direction",
            "kierunek",
            "endStation",
        ],
        "Kierunek nieznany",
    )

    train_number = first_value(
        merged_record,
        [
            "trainNumber",
            "commercialTrainNumber",
            "number",
            "nrPociagu",
            "serviceNumber",
        ],
        "—",
    )

    category = first_value(
        merged_record,
        [
            "commercialCategory",
            "commercialCategoryCode",
            "category",
            "trainCategory",
        ],
        "",
    )

    carrier = first_value(
        merged_record,
        [
            "carrierName",
            "carrier",
            "operatorName",
            "operator",
            " przewoznik",
        ],
        "Przewoźnik",
    )

    platform = first_value(
        merged_record,
        [
            "platform",
            "platformNumber",
            "peron",
        ],
        "—",
    )

    track = first_value(
        merged_record,
        [
            "track",
            "trackNumber",
            "tor",
        ],
        "",
    )

    cancelled_value = first_value(
        merged_record,
        [
            "cancelled",
            "isCancelled",
            "canceled",
            "isCanceled",
        ],
        False,
    )

    status_value = str(
        first_value(
            merged_record,
            [
                "status",
                "trainStatus",
                "operationStatus",
            ],
            "",
        )
    ).lower()

    cancelled = (
        cancelled_value is True
        or str(cancelled_value).lower() == "true"
        or "cancel" in status_value
        or "odwoł" in status_value
        or "odwol" in status_value
    )

    display_number = str(train_number)

    if category:
        category_text = str(category).strip()

        if not display_number.startswith(category_text):
            display_number = (
                f"{category_text} {display_number}"
            ).strip()

    now = datetime.now()

    minutes_until = max(
        0,
        int(
            (actual_time - now).total_seconds()
            // 60
        ),
    )

    return {
        "station_name": str(station_name),
        "planned_time": planned_time or actual_time,
        "current_time": actual_time,
        "minutes_until": minutes_until,
        "direction": str(destination),
        "train_number": display_number,
        "carrier": str(carrier),
        "delay": max(0, delay),
        "platform": str(platform),
        "track": str(track),
        "cancelled": cancelled,
        "raw": record,
    }


@st.cache_data(ttl=90, show_spinner=False)
def get_live_trains(
    station_name: str,
) -> tuple[list[dict[str, Any]], str, int, str]:
    station_id, status_code, error_message = (
        get_station_id(station_name)
    )

    if station_id is None:
        return (
            [],
            "error",
            status_code,
            error_message,
        )

    payload, status_code, error_message = (
        pkp_request(
            "/operations",
            params={
                "stations": station_id,
                "withPlanned": "true",
                "fullRoutes": "true",
                "page": 1,
                "pageSize": 500,
            },
        )
    )

    if status_code != 200:
        return (
            [],
            "error",
            status_code,
            error_message,
        )

    records = extract_records(payload)
    trains: list[dict[str, Any]] = []

    now = datetime.now()
    oldest_allowed = now - timedelta(minutes=3)

    for record in records:
        train = operation_to_train(
            record,
            station_name,
        )

        if train is None:
            continue

        if (
            train["current_time"] < oldest_allowed
            and not train["cancelled"]
        ):
            continue

        trains.append(train)

    trains.sort(
        key=lambda train: train["current_time"]
    )

    unique_trains: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for train in trains:
        unique_key = (
            train["train_number"],
            train["current_time"].strftime(
                "%Y-%m-%d %H:%M"
            ),
            train["direction"],
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)
        unique_trains.append(train)

    return (
        unique_trains[:NUMBER_OF_TRAINS],
        "live",
        200,
        "",
    )


# ============================================================
# DANE TESTOWE
# ============================================================

def stable_number(
    text: str,
    minimum: int,
    maximum: int,
) -> int:
    digest = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    value = int(digest[:8], 16)

    return minimum + value % (
        maximum - minimum + 1
    )


def get_test_directions(
    station: str,
) -> list[str]:
    directions: dict[str, list[str]] = {
        "Kamień Pomorski": [
            "Wysoka Kamieńska",
            "Szczecin Główny",
        ],
        "Wysoka Kamieńska": [
            "Kamień Pomorski",
            "Świnoujście",
            "Szczecin Główny",
        ],
        "Gryfice": [
            "Kołobrzeg",
            "Szczecin Główny",
            "Trzebiatów",
        ],
        "Goleniów": [
            "Szczecin Główny",
            "Świnoujście",
            "Kołobrzeg",
            "Koszalin",
        ],
    }

    return directions.get(
        station,
        [
            "Szczecin Główny",
            "Świnoujście",
            "Kołobrzeg",
        ],
    )


def generate_test_trains(
    station: str,
) -> list[dict[str, Any]]:
    now = datetime.now()
    current_minute = now.replace(
        second=0,
        microsecond=0,
    )

    directions = get_test_directions(station)
    trains: list[dict[str, Any]] = []

    for index in range(NUMBER_OF_TRAINS):
        seed = (
            f"{station}-"
            f"{current_minute:%Y-%m-%d-%H}-"
            f"{index}"
        )

        minutes_until = (
            5
            + index * 14
            + stable_number(
                f"{seed}-offset",
                0,
                7,
            )
        )

        planned_time = (
            current_minute
            + timedelta(minutes=minutes_until)
        )

        delay_options = [0, 0, 0, 2, 4, 7]

        delay = delay_options[
            stable_number(
                f"{seed}-delay",
                0,
                len(delay_options) - 1,
            )
        ]

        current_time = (
            planned_time
            + timedelta(minutes=delay)
        )

        direction = directions[
            stable_number(
                f"{seed}-direction",
                0,
                len(directions) - 1,
            )
        ]

        carrier = (
            "POLREGIO"
            if stable_number(
                f"{seed}-carrier",
                0,
                4,
            ) < 4
            else "PKP Intercity"
        )

        category = (
            "REG"
            if carrier == "POLREGIO"
            else "IC"
        )

        trains.append(
            {
                "planned_time": planned_time,
                "current_time": current_time,
                "minutes_until": max(
                    0,
                    int(
                        (
                            current_time - now
                        ).total_seconds()
                        // 60
                    ),
                ),
                "direction": direction,
                "train_number": (
                    f"{category} "
                    f"{stable_number(
                        f'{seed}-number',
                        80000,
                        89999,
                    )}"
                ),
                "carrier": carrier,
                "delay": delay,
                "platform": str(
                    stable_number(
                        f"{seed}-platform",
                        1,
                        3,
                    )
                ),
                "track": "",
                "cancelled": False,
                "raw": {},
            }
        )

    return sorted(
        trains,
        key=lambda train: train["current_time"],
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
        get_station_id.clear()

    st.caption(
        "Dane API są buforowane przez 90 sekund."
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
# ULUBIONE
# ============================================================

header_left, header_right = st.columns(
    [3, 1]
)

with header_left:
    st.subheader("⭐ Ulubione stacje")

with header_right:
    st.caption("☰ Edycja w panelu bocznym")


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
# POBIERANIE DANYCH
# ============================================================

selected_station = (
    st.session_state.selected_station
)

live_trains, api_mode, api_status, api_error = (
    get_live_trains(selected_station)
)

if api_mode == "live" and live_trains:
    trains = live_trains
    data_mode = "live"

elif api_status in (401, 403):
    trains = generate_test_trains(
        selected_station
    )
    data_mode = "waiting"

elif api_mode == "live" and not live_trains:
    trains = []
    data_mode = "empty"

else:
    trains = generate_test_trains(
        selected_station
    )
    data_mode = "fallback"


# ============================================================
# STATUS API
# ============================================================

if data_mode == "live":
    st.markdown(
        """
        <div class="api-banner api-live">
            ✅ <strong>Dane rzeczywiste PKP PLK</strong>
            — aplikacja jest połączona z API.
        </div>
        """,
        unsafe_allow_html=True,
    )

elif data_mode == "waiting":
    st.markdown(
        """
        <div class="api-banner api-test">
            ⏳ <strong>Klucz PKP oczekuje na aktywację.</strong>
            Do tego czasu wyświetlane są dane testowe.
            Po aktywacji aplikacja przełączy się automatycznie.
        </div>
        """,
        unsafe_allow_html=True,
    )

elif data_mode == "empty":
    st.markdown(
        """
        <div class="api-banner api-live">
            ✅ Połączono z API PKP PLK, ale dla tej stacji
            nie znaleziono najbliższych pociągów.
        </div>
        """,
        unsafe_allow_html=True,
    )

else:
    st.markdown(
        """
        <div class="api-banner api-error">
            ⚠️ <strong>API PKP jest chwilowo niedostępne.</strong>
            Wyświetlane są dane testowe.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# TABLICA
# ============================================================

last_update = datetime.now()

with st.container(border=True):
    st.markdown(
        f'<div class="station-title">'
        f"🚉 {selected_station}"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="update-time">'
        f"Ostatnia aktualizacja: "
        f"{last_update:%H:%M:%S}"
        f"</div>",
        unsafe_allow_html=True,
    )


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
                f"{train['current_time']:%H:%M}"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.markdown(
                f'<div class="train-direction">'
                f"→ {train['direction']}"
                f"</div>",
                unsafe_allow_html=True,
            )

            details_parts = [
                str(train["train_number"]),
                str(train["carrier"]),
            ]

            if train["platform"] not in ("", "—"):
                details_parts.append(
                    f"peron {train['platform']}"
                )

            if train["track"]:
                details_parts.append(
                    f"tor {train['track']}"
                )

            if (
                train["delay"] > 0
                and train["planned_time"]
            ):
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

            if train["cancelled"]:
                status_html = (
                    '<div class="status-wrap">'
                    '<span class="status-pill '
                    'status-cancelled">'
                    '❌ Odwołany'
                    '</span></div>'
                )

            elif train["delay"] == 0:
                status_html = (
                    '<div class="status-wrap">'
                    '<span class="status-pill status-ok">'
                    '✅ Punktualnie'
                    '</span></div>'
                )

            else:
                status_html = (
                    '<div class="status-wrap">'
                    '<span class="status-pill '
                    'status-warn">'
                    f'⚠️ Opóźnienie '
                    f'+{train["delay"]} min'
                    '</span></div>'
                )

            st.markdown(
                status_html,
                unsafe_allow_html=True,
            )


if data_mode == "live":
    st.caption(
        "Dane rzeczywiste: PKP Polskie Linie Kolejowe S.A. "
        "• ustawienia zapisane w Supabase"
    )
else:
    st.caption(
        "Tryb zastępczy: dane testowe "
        "• ustawienia zapisane w Supabase"
    )
