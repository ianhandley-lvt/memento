from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

_NON_SLUG = re.compile(r"[^a-z0-9]+")
_PAGE_PATH = re.compile(r"/wiki/spaces/[^/]+/pages/(\d+)")
_BLOCK_TAGS = frozenset({
    "p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br",
    "blockquote", "table", "ul", "ol", "pre",
})


class ConfluenceURLError(ValueError):
    """A URL is not a recognized Confluence Cloud page link."""


class ConfluenceFetchError(RuntimeError):
    """The Confluence REST API call failed (auth, network, or missing page)."""


@dataclass(frozen=True)
class ConfluencePage:
    base_url: str
    page_id: str
    title: str
    text: str
    version: int
    url: str


def _slug(value: str) -> str:
    return _NON_SLUG.sub("-", value.lower()).strip("-") or "page"


def parse_confluence_url(url: str) -> tuple[str, str]:
    """Extract (base_url, page_id) from a Confluence Cloud page URL.

    Handles both current-style links (`/wiki/spaces/KEY/pages/12345/Title`)
    and the older `/wiki/pages/viewpage.action?pageId=12345` form.
    """

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ConfluenceURLError(f"not an absolute URL: {url!r}")
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    match = _PAGE_PATH.search(parsed.path)
    if match:
        return base_url, match.group(1)

    if parsed.path.endswith("/wiki/pages/viewpage.action"):
        page_ids = parse_qs(parsed.query).get("pageId")
        if page_ids:
            return base_url, page_ids[0]

    raise ConfluenceURLError(
        f"not a recognized Confluence page URL (expected /wiki/spaces/.../pages/<id>/...): {url!r}"
    )


def confluence_source_id(base_url: str, page_id: str) -> str:
    host_slug = _slug(urlparse(base_url).netloc)
    return f"confluence--{host_slug}--{page_id}"


class _StorageToText(HTMLParser):
    """Flattens Confluence storage-format XHTML into readable text for the
    extraction model. Not a faithful HTML/Markdown converter — headings,
    paragraphs, list items, and table rows get line breaks so the shape of
    the source is legible, everything else is just text content in document
    order. Confluence macros (`<ac:structured-macro>`) commonly wrap their
    body in a CDATA section (e.g. code-block bodies); `unknown_decl` below
    is what captures that content, since HTMLParser doesn't otherwise treat
    CDATA specially outside <script>/<style>."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._base_url = base_url
        self._parts: list[str] = []
        self._link_href: str | None = None
        self._link_text_start = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        local_tag = tag.rsplit(":", 1)[-1]
        if local_tag in _BLOCK_TAGS:
            self._parts.append("\n")
        if local_tag.startswith("h") and local_tag[1:].isdigit():
            self._parts.append("#" * int(local_tag[1:]) + " ")
        if local_tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._link_href = href if href.startswith("http") else f"{self._base_url}{href}"
                self._link_text_start = len(self._parts)

    def handle_endtag(self, tag: str) -> None:
        local_tag = tag.rsplit(":", 1)[-1]
        if local_tag == "a" and self._link_href:
            link_text = "".join(self._parts[self._link_text_start:]).strip()
            del self._parts[self._link_text_start:]
            self._parts.append(f"{link_text} ({self._link_href})" if link_text else self._link_href)
            self._link_href = None
        if local_tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def unknown_decl(self, data: str) -> None:
        # `data` is the raw content of a `<![CDATA[...]]>` section.
        self._parts.append(data)

    def text(self) -> str:
        flattened = "".join(self._parts)
        return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", flattened)).strip()


def storage_to_text(storage_html: str, *, base_url: str) -> str:
    converter = _StorageToText(base_url)
    converter.feed(storage_html)
    return converter.text()


def fetch_confluence_page(base_url: str, page_id: str, *, email: str, token: str, timeout: int = 30) -> ConfluencePage:
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    request = urllib.request.Request(
        f"{base_url}/wiki/rest/api/content/{page_id}?expand=body.storage,version",
        headers={"Authorization": f"Basic {credentials}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        reason = "authentication failed (check the Atlassian API token)" if error.code in (401, 403) else str(error)
        raise ConfluenceFetchError(f"Confluence page {page_id} at {base_url}: {reason}") from error
    except urllib.error.URLError as error:
        raise ConfluenceFetchError(f"Confluence page {page_id} at {base_url}: {error.reason}") from error

    storage_value = payload.get("body", {}).get("storage", {}).get("value", "")
    return ConfluencePage(
        base_url=base_url,
        page_id=page_id,
        title=payload.get("title", page_id),
        text=storage_to_text(storage_value, base_url=base_url),
        version=payload.get("version", {}).get("number", 0),
        url=f"{base_url}/wiki{payload.get('_links', {}).get('webui', '')}",
    )
