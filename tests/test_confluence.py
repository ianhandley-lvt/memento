import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from memento.confluence import (
    ConfluenceFetchError,
    ConfluenceURLError,
    confluence_source_id,
    fetch_confluence_page,
    parse_confluence_url,
    storage_to_text,
)


def test_parse_confluence_url_extracts_base_url_and_page_id():
    base_url, page_id = parse_confluence_url(
        "https://liveviewtech.atlassian.net/wiki/spaces/SD/pages/4336746654/Backend+Core+Team"
    )
    assert base_url == "https://liveviewtech.atlassian.net"
    assert page_id == "4336746654"


def test_parse_confluence_url_handles_legacy_viewpage_form():
    base_url, page_id = parse_confluence_url(
        "https://liveviewtech.atlassian.net/wiki/pages/viewpage.action?pageId=12345"
    )
    assert base_url == "https://liveviewtech.atlassian.net"
    assert page_id == "12345"


def test_parse_confluence_url_rejects_non_confluence_url():
    with pytest.raises(ConfluenceURLError):
        parse_confluence_url("https://example.com/some/article")


def test_confluence_source_id_is_stable_for_same_page():
    first = confluence_source_id("https://liveviewtech.atlassian.net", "12345")
    second = confluence_source_id("https://liveviewtech.atlassian.net", "12345")
    assert first == second
    assert "12345" in first


def test_storage_to_text_preserves_headings_and_links():
    html = (
        "<h1>Observability Guild</h1>"
        "<p>See <a href='/wiki/spaces/SD/pages/1/Runbook'>the runbook</a> for details.</p>"
    )
    text = storage_to_text(html, base_url="https://liveviewtech.atlassian.net")
    assert "# Observability Guild" in text
    assert "the runbook (https://liveviewtech.atlassian.net/wiki/spaces/SD/pages/1/Runbook)" in text


def test_storage_to_text_captures_cdata_macro_body():
    html = (
        "<ac:structured-macro ac:name='code'>"
        "<ac:plain-text-body><![CDATA[def handler(): pass]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    )
    text = storage_to_text(html, base_url="https://liveviewtech.atlassian.net")
    assert "def handler(): pass" in text


def _http_response(payload: dict):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    response.__enter__.return_value = response
    return response


def test_fetch_confluence_page_returns_converted_page():
    payload = {
        "title": "Backend Core Team",
        "body": {"storage": {"value": "<p>Hello guild.</p>"}},
        "version": {"number": 3},
        "_links": {"webui": "/spaces/SD/pages/4336746654"},
    }
    with patch("urllib.request.urlopen", return_value=_http_response(payload)):
        page = fetch_confluence_page(
            "https://liveviewtech.atlassian.net", "4336746654", email="ian@lvt.com", token="secret"
        )

    assert page.title == "Backend Core Team"
    assert "Hello guild." in page.text
    assert page.version == 3
    assert page.url == "https://liveviewtech.atlassian.net/wiki/spaces/SD/pages/4336746654"


def test_fetch_confluence_page_reports_auth_failure_clearly():
    error = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=None)
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(ConfluenceFetchError, match="authentication failed"):
            fetch_confluence_page("https://liveviewtech.atlassian.net", "1", email="ian@lvt.com", token="bad")
