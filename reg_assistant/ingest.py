"""Fetch a small explicit manifest; preserve provenance and fail on partial runs."""

import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class MainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = 0
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "main":
            self.active += 1
        if self.active:
            if tag in {"script", "style", "nav", "aside"}:
                self.skip += 1
            if tag in {"p", "li", "h1", "h2", "h3", "h4", "br"} and not self.skip:
                self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.active and tag in {"script", "style", "nav", "aside"}:
            self.skip = max(0, self.skip - 1)
        if tag == "main":
            self.active = max(0, self.active - 1)

    def handle_data(self, data):
        if self.active and not self.skip:
            self.parts.append(data)

    def text(self):
        return "\n".join(line for line in (" ".join(part.split()) for part in "".join(self.parts).splitlines()) if line)


def ingest(manifest, output, raw_dir):
    sources = json.loads(Path(manifest).read_text())
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    documents = []
    for source in sources:
        parsed = urlparse(source["url"])
        if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".gov.au"):
            raise ValueError("Sources must be HTTPS Australian government URLs")
        if not source["id"] or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in source["id"]):
            raise ValueError("Source ids must contain only lowercase letters, digits, hyphens and underscores")
        request = Request(source["url"], headers={"User-Agent": "AustralianRegulatoryResearch/0.1"})
        with urlopen(request, timeout=30) as response:
            final_url = response.geturl()
            final = urlparse(final_url)
            if final.scheme != "https" or not (final.hostname or "").endswith(".gov.au"):
                raise ValueError("Source redirected outside Australian government HTTPS")
            if "text/html" not in response.headers.get("Content-Type", ""):
                raise ValueError("This importer accepts HTML pages only")
            raw = response.read(5_000_001)
            encoding = response.headers.get_content_charset() or "utf-8"
        if len(raw) > 5_000_000:
            raise ValueError("Source exceeds 5 MB limit")
        parser = MainText()
        parser.feed(raw.decode(encoding))
        text = parser.text()
        if len(text.split()) < 50:
            raise ValueError(f"No substantial <main> content found in {source['url']}")
        (raw_dir / f"{source['id']}.html").write_bytes(raw)
        documents.append({**source, "url": final_url, "text": text, "source_kind": "official_page",
                          "retrieved_at": datetime.now(timezone.utc).isoformat(),
                          "sha256": hashlib.sha256(raw).hexdigest()})
    if not documents:
        raise ValueError("Empty source manifest")
    # Do not replace a working corpus if any source failed.
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(json.dumps(doc) + "\n" for doc in documents))
    temporary.replace(output)
    return len(documents)
