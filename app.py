from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

import streamlit as st


# ============================================================
# KONFIGURACJA
# ============================================================

st.set_page_config(
    page_title="Moja Tablica Kolejowa",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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
            padding-top: 1.2rem;
            padding-bottom: 3rem;
        }

        .main-title {
            font-size: 2.1rem;
            font-weight: 800;
            margin-bottom: 0;
        }

        .subtitle {
            color: #A8ADB7;
            margin-top: 0.2rem;
            margin-bottom: 1.3rem;
        }

        .test-banner {
            border-radius: 10px;
            padding: 0.75rem 0.9rem;
            margin-bottom: 1rem;
            background: rgba(255, 179, 71, 0.12);
            border: 1px solid rgba(255, 179, 71, 0.35);
        }

        .station-title {
            font-size: 1.55rem;
            font-weight: 750;
        }

        .update-time {
            color: #A8ADB7;
            font-size: 0.92rem;
        }

        div[data-testid="stButton"] > button {
            min-height: 2.8rem;
            border-radius: 10px;
            font-weight: 650;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 14px;
        }

        @media (max-width: 640px) {
            .main-title {
                font-size: 1.7rem;
            }

            .station-title {
                font-size: 1.3rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# STAN APLIKACJI
# ============================================================

if "favorites" not in st.session_state:
    st.session_state.favorites = DEFAULT_FAVORITES.copy()

if "selected_station" not in st.session_state:
    st.session_state.selected_station = DEFAULT_FAVORITES[0]


# ============================================================
# CALLBACKI
# ============================================================

def choose_station(station: str) -> None:
    st.session_state.selected_station = station


def add_favorite() -> None:
    station = st.session_state.station_to_add

    if station and station not in st.session_state.favorites:
        st.session_state.favorites.append(station)


def remove_favorite(station: str) -> None:
    if len(st.session_state.favorites) <= 1:
        return

    if station in st.session_state.favorites:
        st.session_state.favorites.remove(station)

    if st.session_state.selected_station == station:
        st.session_state.selected_station = st.session_state.favorites[0]


# ============================================================
# DANE TESTOWE
# ============================================================

def stable_number(text: str, minimum: int, maximum: int) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)

    return minimum + value % (maximum - minimum + 1)


def get_test_directions(station: str) -> list[str]:
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
        "Międzyzdroje": [
            "Świnoujście",
            "Szczecin Główny",
        ],
        "Świnoujście": [
            "Szczecin Główny",
            "Poznań Główny",
            "Warszawa Wschodnia",
        ],
        "Szczecin Główny": [
            "Świnoujście",
            "Kołobrzeg",
            "Koszalin",
            "Poznań Główny",
            "Warszawa Wschodnia",
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
    number_of_trains: int = NUMBER_OF_TRAINS,
) -> list[dict[str, Any]]:
    now = datetime.now()
    current_minute = now.replace(second=0, microsecond=0)
    directions = get_test_directions(station)

    trains: list[dict[str, Any]] = []

    for index in range(number_of_trains):
        seed = f"{station}-{current_minute:%Y-%m-%d-%H}-{index}"

        minutes_until = (
            5
            + index * 14
            + stable_number(
                f"{seed}-offset",
                0,
                7,
            )
        )

        planned_time = current_minute + timedelta(
            minutes=minutes_until
        )

        delay_options = [0, 0, 0, 2, 4, 7]

        delay_index = stable_number(
            f"{seed}-delay",
            0,
            len(delay_options) - 1,
        )

        delay = delay_options[delay_index]

        current_time = planned_time + timedelta(
            minutes=delay
        )

        direction_index = stable_number(
            f"{seed}-direction",
            0,
            len(directions) - 1,
        )

        train_number = stable_number(
            f"{seed}-number",
            80000,
            89999,
        )

        carrier = (
            "POLREGIO"
            if stable_number(
                f"{seed}-carrier",
                0,
                4,
            ) < 4
            else "PKP Intercity"
        )

        train_category = (
            "REG"
            if carrier == "POLREGIO"
            else "IC"
        )

        minutes_to_train = max(
            0,
            int(
                (current_time - now).total_seconds()
                // 60
            ),
        )

        trains.append(
            {
                "planned_time": planned_time,
                "current_time": current_time,
                "minutes_until": minutes_to_train,
                "direction": directions[direction_index],
                "train_number": f"{train_category} {train_number}",
                "carrier": carrier,
                "delay": delay,
                "platform": stable_number(
                    f"{seed}-platform",
                    1,
                    3,
                ),
            }
        )

    return sorted(
        trains,
        key=lambda train: train["current_time"],
    )


# ============================================================
# PANEL BOCZNY — EDYCJA ULUBIONYCH
# ============================================================

with st.sidebar:
    st.header("⚙️ Ustawienia")

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
        st.info("Wszystkie stacje są już dodane.")

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
                disabled=len(st.session_state.favorites) <= 1,
            )

    st.caption(
        "Zmiany są zapisywane tylko w bieżącej sesji."
    )


# ============================================================
# NAGŁÓWEK
# ============================================================

st.markdown(
    '<div class="main-title">'
    "🚆 Moja Tablica Kolejowa"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "Pięć najbliższych pociągów dla wybranej stacji"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="test-banner">
        🧪 <strong>Tryb testowy:</strong>
        wyświetlane godziny i pociągi są na razie przykładowe.
        Po aktywacji klucza podłączymy prawdziwe dane PKP PLK.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ULUBIONE
# ============================================================

header_left, header_right = st.columns([3, 1])

with header_left:
    st.subheader("⭐ Ulubione stacje")

with header_right:
    st.caption("☰ Edycja w panelu bocznym")


favorites = st.session_state.favorites

favorite_columns = st.columns(
    min(4, max(1, len(favorites)))
)

for index, station in enumerate(favorites):
    column = favorite_columns[
        index % len(favorite_columns)
    ]

    with column:
        selected = (
            station == st.session_state.selected_station
        )

        st.button(
            f"✓ {station}" if selected else station,
            key=f"favorite_{index}_{station}",
            type="primary" if selected else "secondary",
            on_click=choose_station,
            args=(station,),
            use_container_width=True,
        )


# ============================================================
# WYBÓR STACJI
# ============================================================

selected_index = AVAILABLE_STATIONS.index(
    st.session_state.selected_station
)

st.selectbox(
    "🔎 Wybierz inną stację:",
    options=AVAILABLE_STATIONS,
    index=selected_index,
    key="main_station_selector",
    on_change=lambda: choose_station(
        st.session_state.main_station_selector
    ),
)


# ============================================================
# TABLICA
# ============================================================

selected_station = st.session_state.selected_station
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
        f"Ostatnia aktualizacja: {last_update:%H:%M:%S}"
        f"</div>",
        unsafe_allow_html=True,
    )


trains = generate_test_trains(selected_station)

for train in trains:
    with st.container(border=True):
        left_column, right_column = st.columns([3, 1])

        with left_column:
            st.markdown(
                f"## {train['current_time']:%H:%M}"
            )

            st.markdown(
                f"### → {train['direction']}"
            )

            details = (
                f"**{train['train_number']}**"
                f" · {train['carrier']}"
                f" · peron {train['platform']}"
            )

            if train["delay"] > 0:
                details += (
                    f" · planowo "
                    f"{train['planned_time']:%H:%M}"
                )

            st.caption(details)

        with right_column:
            st.markdown(
                f"### za {train['minutes_until']} min"
            )

            if train["delay"] == 0:
                st.success(
                    "Punktualnie",
                    icon="✅",
                )
            else:
                st.warning(
                    f"Opóźnienie +{train['delay']} min",
                    icon="⚠️",
                )


st.caption(
    "Wersja testowa • następny etap: "
    "podłączenie oficjalnego API PKP PLK"
)
