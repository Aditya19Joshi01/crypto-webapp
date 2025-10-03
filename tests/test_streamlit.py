import os


def test_streamlit_file_contains_expected_strings():
    # Read the streamlit_app.py and check it contains expected sections so we know
    # the developer UI exists without importing heavy streamlit/pandas binaries.
    path = os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py")
    path = os.path.abspath(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Backend base URL" in content or "DEFAULT_BACKEND" in content
    assert "Price Explorer" in content
    assert "TVL Explorer" in content
