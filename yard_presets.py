"""SETTING_SPECS-Permalink-Muster, Presets und Zufalls-Seed-Button (Standardmuster aus dem
OR-Demo-Portfolio, siehe z.B. berth_presets.py)."""

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

import yard_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None


SETTING_SPECS = {
    "n_jobs_slider": SettingSpec("nj", int, C.N_JOBS_DEFAULT, *C.N_JOBS_RANGE),
    "n_vehicles_slider": SettingSpec("nv", int, C.N_VEHICLES_DEFAULT, *C.N_VEHICLES_RANGE),
    "arrival_window_slider": SettingSpec("aw", int, C.ARRIVAL_WINDOW_DEFAULT, *C.ARRIVAL_WINDOW_RANGE),
    "peak_slider": SettingSpec("pk", int, C.PEAK_PCT_DEFAULT, *C.PEAK_PCT_RANGE),
    "buffer_slider": SettingSpec("bf", int, C.BUFFER_DEFAULT, *C.BUFFER_RANGE),
    "departure_slider": SettingSpec("ds", int, C.DEPARTURE_PCT_DEFAULT, *C.DEPARTURE_PCT_RANGE),
    "yard_length_slider": SettingSpec("yl", int, C.YARD_LENGTH_DEFAULT, *C.YARD_LENGTH_RANGE),
    "n_doors_slider": SettingSpec("nd", int, C.N_DOORS_DEFAULT, *C.N_DOORS_RANGE),
    "seed_input": SettingSpec("seed", int, C.RANDOM_SEED_DEFAULT, *C.RANDOM_SEED_RANGE),
}

PRESET_TO_STATE = {
    "n_jobs": "n_jobs_slider",
    "n_vehicles": "n_vehicles_slider",
    "arrival_window": "arrival_window_slider",
    "peak_pct": "peak_slider",
    "buffer": "buffer_slider",
    "departure_pct": "departure_slider",
    "yard_length": "yard_length_slider",
    "n_doors": "n_doors_slider",
    "seed": "seed_input",
}


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
                if isinstance(value, float) and not math.isfinite(value):
                    continue
                if spec.lo is not None:
                    value = max(spec.lo, value)
                if spec.hi is not None:
                    value = min(spec.hi, value)
                st.session_state[state_key] = value
            except (ValueError, TypeError):
                pass
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """values: dict state_key -> aktueller Wert (aus den Widgets, nicht aus session_state, damit
    dieselbe Änderung, die gerade gerendert wurde, auch sofort in der Adresszeile landet)."""
    try:
        for state_key, value in values.items():
            spec = SETTING_SPECS[state_key]
            st.query_params[spec.url_param] = str(int(value)) if spec.caster is int else str(value)
    except Exception:
        pass


def apply_preset(name):
    for preset_key, value in C.PRESETS[name].items():
        st.session_state[PRESET_TO_STATE[preset_key]] = value


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, 2_000_000_000)
