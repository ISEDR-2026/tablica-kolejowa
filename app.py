from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ============================================================
# KONFIGURACJA APLIKACJI
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

# Tymczasowa lista stacji.
# Po podłączeniu API zostanie zastąpiona pełnym wykazem stacji.
AVAILABLE_STATIONS = [
    "Kamień Pomorski",
    "Wysoka Kamieńska",
    "Gryfice",
    "Goleniów",
    "Międzyzdroje",
    "Świnoujście",
    "Świnoujście Centrum",
    "Szczecin Główny",
    "Szczecin Dąbie",
    "Szczecin Zdroje",
    "Stargard",
    "Koszalin",
    "Kołobrzeg",
    "Trzebiatów",
    "Nowogard",
    "Wolin Pomorski",
    "Międzywodzie",
    "Recław",
]

REFRESH_INTERVAL_SECONDS = 60
NUMBER_OF_TRAINS = 5


# ============================================================
# STYL APLIKACJI
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

        .station-header {
            padding: 1rem 1.2rem;
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 14px;
            background: rgba(255, 255, 255, 0.04);
            margin-top: 0.8rem;
            margin-bottom: 1rem;
        }

        .station-name {
            font-size: 1.55rem;
            font-weight: 750;
        }

        .update-time {
            color: #A8ADB7;
            font-size: 0.92rem;
        }

        .train-card {
            padding: 0.95rem 1rem;
            margin-bottom: 0.7rem;
            border-radius: 14px;
            border: 1px solid rgba(255, 255, 255, 0.10);
            background: rgba(255, 255, 255, 0.035);
        }

        .train-time {
            font-size: 1.55rem;
            font-weight: 800;
        }

        .train-direction {
            font-size: 1.08rem;
            font-weight: 650;
        }

        .train-details {
            color: #A8ADB7;
            font-size: 0.9rem;
            margin-top: 0.25rem;
        }

        .delay-ok {
            color: #58D68D;
            font-weight: 700;
        }

        .delay-warning {
            color: #FFB347;
            font-weight: 700;
        }

        .test-banner {
            border-radius: 10px;
            padding: 0.65rem 0.85rem;
            margin-bottom: 1rem;
            background: rgba(255, 179, 71, 0.12);
            border: 1px solid rgba(255, 179, 71, 0.35);
        }

        div[data-testid="stButton"] > button {
            min-height: 2.8rem;
            border-radius: 10px;
            font-weight: 650;
        }

        @media (max-width: 640px) {
            .main-title {
                font-size: 1.7rem;
            }

            .station-name {
                font-size: 1.3rem;
            }

            .train-time {
                font-size: 1.35rem;
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
    """Ustawia wartości początkowe aplikacji."""

    if "favorites" not in st.session_state:
        st.session_state.favorites = DEFAULT_FAVORITES.copy()

    if "selected_station" not in st.session_state:
        st.session_state.selected_station = DEFAULT_FAVORITES[0]

    if "show_favorites_editor" not in st.session_state:
        st.session_state.show_favorites_editor = False


initialize_state()


# Automatyczne odświeżenie strony co 60 sekund.
# Funkcję wywołujemy tylko raz w całym skrypcie.
st_autorefresh(
    interval=REFRESH_INTERVAL_SECONDS * 1000,
    key="train_board_refresh",
)


# ============================================================
# DANE TESTOWE
# ============================================================

def stable_number(text: str, minimum: int, maximum: int) -> int:
    """
    Tworzy powtarzalną liczbę na podstawie tekstu.
    Dzięki temu dane testowe nie zmieniają się losowo przy każdym kliknięciu.
    """

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)

    return minimum + value % (maximum - minimum + 1)


def get_test_directions(station: str) -> list[str]:
    """Zwraca przykładowe kierunki dla wybranej stacji."""

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
    """
    Generuje tymczasową listę najbliższych pociągów.

    Po aktywacji API ta funkcja zostanie zastąpiona pobieraniem
    prawdziwych danych z PKP PLK.
    """

    now = datetime.now()
    current_minute = now.replace(second=0, microsecond=0)
    directions = get_test_directions(station)

    trains: list[dict[str, Any]] = []

    for index in range(number_of_trains):
        seed = f"{station}-{current_minute:%Y-%m-%d-%H}-{index}"

        minutes_until = 5 + index * 14 + stable_number(
            f"{seed}-offset",
            0,
            7,
        )

        planned_time = current_minute + timedelta(minutes=minutes_until)

        delay_options = [0, 0, 0, 2, 4, 7]
        delay_index = stable_number(
            f"{seed}-delay",
            0,
            len(delay_options) - 1,
        )
        delay = delay_options[delay_index]

        current_time = planned_time + timedelta(minutes=delay)

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
            if stable_number(f"{seed}-carrier", 0, 4) < 4
            else "PKP Intercity"
        )

        train_category = "REG" if carrier == "POLREGIO" else "IC"

        trains.append(
            {
                "planned_time": planned_time,
                "current_time": current_time,
                "minutes_until": max(
                    0,
                    int((current_time - now).total_seconds() // 60),
                ),
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

    return sorted(trains, key=lambda train: train["current_time"])


# ============================================================
# OBSŁUGA ULUBIONYCH
# ============================================================

def select_station(station: str) -> None:
    """Ustawia aktualnie wybraną stację."""

    st.session_state.selected_station = station


def toggle_favorites_editor() -> None:
    """Pokazuje lub ukrywa edytor ulubionych."""

    st.session_state.show_favorites_editor = (
        not st.session_state.show_favorites_editor
    )


def save_favorites() -> None:
    """Zapisuje ulubione wybrane w edytorze."""

    selected = st.session_state.favorites_editor

    if not selected:
        st.warning("Lista ulubionych musi zawierać przynajmniej jedną stację.")
        return

    st.session_state.favorites = selected

    if st.session_state.selected_station not in selected:
        st.session_state.selected_station = selected[0]

    st.session_state.show_favorites_editor = False
    st.success("Lista ulubionych została zapisana.")


# ============================================================
# INTERFEJS
# ============================================================

st.markdown(
    '<div class="main-title">🚆 Moja Tablica Kolejowa</div>',
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
# SZYBKI WYBÓR ULUBIONYCH
# ============================================================

favorite_header_col, editor_button_col = st.columns([3, 1])

with favorite_header_col:
    st.subheader("⭐ Ulubione stacje")

with editor_button_col:
    st.button(
        "⚙️ Edytuj ulubione",
        use_container_width=True,
        on_click=toggle_favorites_editor,
    )


favorites = st.session_state.favorites
number_of_columns = min(4, max(1, len(favorites)))
favorite_columns = st.columns(number_of_columns)

for index, station in enumerate(favorites):
    column = favorite_columns[index % number_of_columns]

    with column:
        is_selected = station == st.session_state.selected_station
        button_label = f"✓ {station}" if is_selected else station

        if st.button(
            button_label,
            key=f"favorite_{station}",
            use_container_width=True,
            type="primary" if is_selected else "secondary",
        ):
            select_station(station)
            st.rerun()


# ============================================================
# EDYCJA ULUBIONYCH
# ============================================================

if st.session_state.show_favorites_editor:
    with st.container(border=True):
        st.subheader("⚙️ Edycja ulubionych stacji")

        st.multiselect(
            "Wybierz stacje, które mają być widoczne jako szybkie przyciski:",
            options=AVAILABLE_STATIONS,
            default=st.session_state.favorites,
            key="favorites_editor",
            placeholder="Wybierz jedną lub więcej stacji",
        )

        save_col, cancel_col = st.columns(2)

        with save_col:
            st.button(
                "💾 Zapisz ulubione",
                use_container_width=True,
                type="primary",
                on_click=save_favorites,
            )

        with cancel_col:
            if st.button(
                "Anuluj",
                use_container_width=True,
            ):
                st.session_state.show_favorites_editor = False
                st.rerun()


# ============================================================
# WYSZUKIWANIE INNEJ STACJI
# ============================================================

selected_index = (
    AVAILABLE_STATIONS.index(st.session_state.selected_station)
    if st.session_state.selected_station in AVAILABLE_STATIONS
    else 0
)

selected_from_list = st.selectbox(
    "🔎 Wybierz inną stację:",
    options=AVAILABLE_STATIONS,
    index=selected_index,
)

if selected_from_list != st.session_state.selected_station:
    select_station(selected_from_list)
    st.rerun()


# ============================================================
# TABLICA POCIĄGÓW
# ============================================================

selected_station = st.session_state.selected_station
last_update = datetime.now()

st.markdown(
    f"""
    <div class="station-header">
        <div class="station-name">🚉 {selected_station}</div>
        <div class="update-time">
            Ostatnia aktualizacja: {last_update:%H:%M:%S}
            • automatyczne odświeżanie co {REFRESH_INTERVAL_SECONDS} sekund
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

trains = generate_test_trains(selected_station)

for train in trains:
    delay = train["delay"]

    if delay == 0:
        delay_html = '<span class="delay-ok">punktualnie</span>'
    else:
        delay_html = (
            f'<span class="delay-warning">opóźnienie +{delay} min</span>'
        )

    planned_information = ""

    if delay > 0:
        planned_information = (
            f" • planowo {train['planned_time']:%H:%M}"
        )

    st.markdown(
        f"""
        <div class="train-card">
            <div style="
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                align-items: center;
            ">
                <div>
                    <div class="train-time">
                        {train['current_time']:%H:%M}
                    </div>

                    <div class="train-direction">
                        → {train['direction']}
                    </div>

                    <div class="train-details">
                        {train['train_number']}
                        • {train['carrier']}
                        • peron {train['platform']}
                        {planned_information}
                    </div>
                </div>

                <div style="text-align: right;">
                    <div style="
                        font-size: 1.15rem;
                        font-weight: 750;
                        margin-bottom: 0.2rem;
                    ">
                        za {train['minutes_until']} min
                    </div>

                    <div>
                        {delay_html}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# WIDOK TABELARYCZNY
# ============================================================

with st.expander("📋 Pokaż widok tabelaryczny"):
    table_data = []

    for train in trains:
        table_data.append(
            {
                "Aktualnie": train["current_time"].strftime("%H:%M"),
                "Planowo": train["planned_time"].strftime("%H:%M"),
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
    "Wersja testowa • następny etap: podłączenie oficjalnego API PKP PLK"
)
