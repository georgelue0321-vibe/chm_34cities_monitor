from pathlib import Path


HEADER_PATH = (
    Path(__file__).resolve().parents[1]
    / "china_housing_monitor"
    / "report"
    / "templates"
    / "header.html"
)
STYLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "china_housing_monitor"
    / "report"
    / "static"
    / "style.css"
)


def test_city_nav_is_independent_sticky_region():
    html = HEADER_PATH.read_text(encoding="utf-8")
    nav_start = html.index("<!-- Tier Navigation Bar -->")
    header_section = html[:nav_start]
    nav_section = html[nav_start:]

    assert "<header" in header_section
    assert "sticky top-0 z-50" not in header_section
    assert "sticky top-0 z-50" in nav_section
    assert html.index("</header>") < nav_start


def test_expanded_city_nav_scrolls_only_when_content_overflows():
    css = STYLE_PATH.read_text(encoding="utf-8")

    assert "max-height: calc(100dvh - 3.75rem);" in css
    assert "overflow-y: auto;" in css
    assert "overscroll-behavior-y: contain;" in css


if __name__ == "__main__":
    test_city_nav_is_independent_sticky_region()
    print("PASS: city navigation is an independent sticky region")
