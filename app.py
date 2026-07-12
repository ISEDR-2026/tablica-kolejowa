from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
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
# WYGLĄD
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

def initialize_state() -> None:
    if "favorites" not in st.session_state:
        st.session_state.favorites = DEFAULT_FAVORITES.copy()

    if "selected_station" not in st.session_state:
        st.session_state.selected_station = DEFAULT_FAVORITES[0]

    if "show_favorites_editor" not in st.session_state:
        st.session_state.show_favorites_editor = False


initialize_state()


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
# OPERACJE NA STACJACH
# ============================================================

def select_station(station: str) -> None:
    st.session_state.selected_station = station


def add_favorite(station: str) -> None:
    if station not in st.session_state.favorites:
        st.session_state.favorites.append(station)


def remove_favorite(station: str) -> None:
    if len(st.session_state.favorites) <= 1:
        st.warning(
            "Musi pozostać przynajmniej jedna ulubiona stacja."
        )
        return

    st.session_state.favorites.remove(station)

    if st.session_state.selected_station == station:
        st.session_state.selected_station = (
            st.session_state.favorites[0]
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
# ULUBIONE STACJE
# ============================================================

favorite_header_col, editor_button_col = st.columns([3, 1])

with favorite_header_col:
    st.subheader("⭐ Ulubione stacje")

with editor_button_col:
    if st.button(
        "⚙️ Edytuj ulubione",
        use_container_width=True,
        key="open_favorites_editor",
    ):
        st.session_state.show_favorites_editor = (
            not st.session_state.show_favorites_editor
        )
        st.rerun()


favorites = st.session_state.favorites
number_of_columns = min(4, max(1, len(favorites)))
favorite_columns = st.columns(number_of_columns)

for index, station in enumerate(favorites):
    column = favorite_columns[index % number_of_columns]

    with column:
        is_selected = (
            station == st.session_state.selected_station
        )

        label = (
            f"✓ {station}"
            if is_selected
            else station
        )

        if st.button(
            label,
            key=f"favorite_station_{index}",
            use_container_width=True,
            type="primary" if is_selected else "secondary",
        ):
            select_station(station)
            st.rerun()


# ============================================================
# BEZPIECZNY EDYTOR ULUBIONYCH
# ============================================================

if st.session_state.show_favorites_editor:
    st.divider()
    st.subheader("⚙️ Edycja ulubionych stacji")

    stations_to_add = [
        station
        for station in AVAILABLE_STATIONS
        if station not in st.session_state.favorites
    ]

    if stations_to_add:
        add_column, button_column = st.columns([3, 1])

        with add_column:
            station_to_add = st.selectbox(
                "Wybierz stację do dodania:",
                options=stations_to_add,
                key="station_to_add",
            )

        with button_column:
            st.write("")

            if st.button(
                "➕ Dodaj",
                use_container_width=True,
                key="add_favorite_button",
            ):
                add_favorite(station_to_add)
                st.rerun()
    else:
        st.info("Wszystkie dostępne stacje są już w ulubionych.")

    st.markdown("#### Obecne ulubione")

    for index, station in enumerate(
        st.session_state.favorites.copy()
    ):
        name_column, remove_column = st.columns([3, 1])

        with name_column:
            st.write(f"⭐ {station}")

        with remove_column:
            if st.button(
                "🗑️ Usuń",
                key=f"remove_favorite_{index}",
                use_container_width=True,
                disabled=(
                    len(st.session_state.favorites) <= 1
                ),
            ):
                remove_favorite(station)
                st.rerun()

    if st.button(
        "✅ Zakończ edycję",
        use_container_width=True,
        key="close_favorites_editor",
    ):
        st.session_state.show_favorites_editor = False
        st.rerun()

    st.divider()


# ============================================================
# WYBÓR INNEJ STACJI
# ============================================================

if st.session_state.selected_station in AVAILABLE_STATIONS:
    selected_index = AVAILABLE_STATIONS.index(
        st.session_state.selected_station
    )
else:
    selected_index = 0

selected_from_list = st.selectbox(
    "🔎 Wybierz inną stację:",
    options=AVAILABLE_STATIONS,
    index=selected_index,
    key="main_station_selector",
)

if selected_from_list != st.session_state.selected_station:
    select_station(selected_from_list)
    st.rerun()


# ============================================================
# WYBRANA STACJA
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
        f"Ostatnia aktualizacja: {last_update:%H:%M:%S} "
        f"• odśwież stronę, aby pobrać nowe dane"
        f"</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# POCIĄGI
# ============================================================

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


# ============================================================
# WIDOK TABELARYCZNY
# ============================================================

with st.expander("📋 Pokaż widok tabelaryczny"):
    table_data = []

    for train in trains:
        table_data.append(
            {
                "Aktualnie": train[
                    "current_time"
                ].strftime("%H:%M"),
                "Planowo": train[
                    "planned_time"
                ].strftime("%H:%M"),
                "Za": f"{train['minutes_until']} min",
                "Pociąg": train["train_number"],
                "Kierunek": train["direction"],
                "Przewoźnik": train["carrier"],
                "Opóźnienie": (
                    "0 min"
                    if train["delay"] == 0
                    else f"+{train['delay']} min"
                ),
                "Peron": train["platform"],
            }
        )

    dataframe = pd.DataFrame(table_data)

    st.dataframe(
        dataframe,
        hide_index=True,
        use_container_width=True,
    )


st.caption(
    "Wersja testowa • następny etap: "
    "podłączenie oficjalnego API PKP PLK"
)
