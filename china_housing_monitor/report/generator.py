"""HTML report generator for China Housing Monitor.

Reads templates, CSS, and JS files, injects data, and writes the final HTML.
"""
import os
import json

from ..config import REPORT_PATH
from ..data.payload import fetch_data_payload

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def _read_file(directory, filename):
    """Read a file and return its contents."""
    path = os.path.join(directory, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def generate_html_report():
    """Compile SQLite dataset into the redesigned standalone responsive HTML interpretation terminal."""
    payload = fetch_data_payload()
    json_data = json.dumps(payload, ensure_ascii=False)

    # Read all template and static files
    base_html = _read_file(TEMPLATE_DIR, "base.html")
    css_content = _read_file(STATIC_DIR, "style.css")
    header_html = _read_file(TEMPLATE_DIR, "header.html")
    left_column_html = _read_file(TEMPLATE_DIR, "left_column.html")
    right_column_html = _read_file(TEMPLATE_DIR, "right_column.html")
    js_nav = _read_file(STATIC_DIR, "nav.js")
    js_gauge = _read_file(STATIC_DIR, "gauge.js")
    js_rankings = _read_file(STATIC_DIR, "rankings.js")
    js_dashboard = _read_file(STATIC_DIR, "dashboard.js")
    js_charts = _read_file(STATIC_DIR, "charts.js")
    js_map = _read_file(STATIC_DIR, "map.js")
    china_geo_json = _read_file(STATIC_DIR, "china.json")

    # Assemble the final HTML by replacing placeholders
    html_content = base_html
    html_content = html_content.replace("{{CSS_CONTENT}}", css_content)
    html_content = html_content.replace("{{JSON_DATA}}", json_data)
    html_content = html_content.replace("{{CHINA_GEO_JSON}}", china_geo_json)
    html_content = html_content.replace("{{HEADER_CONTENT}}", header_html)
    html_content = html_content.replace("{{LEFT_COLUMN_CONTENT}}", left_column_html)
    html_content = html_content.replace("{{RIGHT_COLUMN_CONTENT}}", right_column_html)
    html_content = html_content.replace("{{JS_NAV}}", js_nav)
    html_content = html_content.replace("{{JS_GAUGE}}", js_gauge)
    html_content = html_content.replace("{{JS_RANKINGS}}", js_rankings)
    html_content = html_content.replace("{{JS_DASHBOARD}}", js_dashboard)
    html_content = html_content.replace("{{JS_CHARTS}}", js_charts)
    html_content = html_content.replace("{{JS_MAP}}", js_map)

    try:
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Master standalone dashboard compiled successfully at: {REPORT_PATH}")
    except Exception as e:
        print(f"Error compiling HTML dashboard: {e}")
