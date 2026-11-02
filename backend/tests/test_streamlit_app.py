from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_dashboard_renders_without_optional_api_services():
    app_path = Path(__file__).resolve().parents[2] / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=10).run()

    assert not app.exception
    assert any("VoltGrid Mumbai" in element.value for element in app.title)
    assert "Overview" in app.radio[0].options


def test_streamlit_navigation_shows_offline_database_message():
    app_path = Path(__file__).resolve().parents[2] / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=10).run()
    app.radio[0].set_value("Database").run()

    assert not app.exception
    assert any("Database statistics are unavailable" in element.value for element in app.error)


def test_streamlit_session_page_explains_missing_backend():
    app_path = Path(__file__).resolve().parents[2] / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=10).run()
    app.radio[0].set_value("Charging sessions").run()

    assert not app.exception
    assert any("Session history unavailable" in element.value for element in app.error)
