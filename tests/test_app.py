"""End-to-end Smoke-Tests via Streamlits offiziellem AppTest-Framework: laden app.py mit den
Standardeinstellungen und allen Presets und prüfen, dass kein Python-Fehler auftritt. Fehler wie
`StreamlitDuplicateElementId` (zwei st.plotly_chart-Aufrufe ohne eindeutiges key= mit zufällig
identischem Inhalt) liegen in app.py's Widget-Verdrahtung selbst und sind nur durch einen echten
End-to-End-Lauf zu finden."""

import os

import pytest
from streamlit.testing.v1 import AppTest

import yard_constants as C

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def test_app_loads_without_exception():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=120)
    assert not at.exception, [str(e) for e in at.exception]


@pytest.mark.parametrize("preset_index", range(len(C.PRESETS)))
def test_app_loads_with_each_preset(preset_index):
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=120)
    at.button[preset_index].click()
    at.run(timeout=120)
    assert not at.exception, [str(e) for e in at.exception]
