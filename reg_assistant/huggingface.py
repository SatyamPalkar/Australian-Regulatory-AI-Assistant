"""Import a bounded, pinned selection of actual legislation from Hugging Face."""
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

AKN = {"a": "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"}
MAX_DOWNLOAD = 20_000_000


def checked_bytes(raw, expected):
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Source checksum mismatch: refusing changed or incomplete dataset bytes")
    return raw


def download_file(dataset, revision, filename, expected, cache):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Pin the dataset to a complete 40-character commit revision")
    path = Path(cache) / Path(filename).name
    if path.exists():
        return checked_bytes(path.read_bytes(), expected)
    url = f"https://huggingface.co/datasets/{dataset}/resolve/{revision}/{quote(filename, safe='/')}"
    request = Request(url, headers={"User-Agent": "AustralianRegulatoryResearch/0.2"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                raw = response.read(MAX_DOWNLOAD + 1)
            if len(raw) > MAX_DOWNLOAD:
                raise ValueError("Dataset file exceeds the 20 MB download limit")
            checked_bytes(raw, expected)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_bytes(raw)
            temp.replace(path)
            return raw
        except (HTTPError, URLError, TimeoutError) as exc:
            if isinstance(exc, HTTPError) and exc.code < 500 and exc.code != 429:
                raise
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def extract_sections(raw_xml, index, manifest, retrieved_at):
    root = ET.fromstring(raw_xml)
    metadata = index["acts"][manifest["slug"]]
    expression_date = root.find(".//a:FRBRExpression/a:FRBRdate", AKN)
    if expression_date is None or expression_date.get("date") != metadata["effective_date"]:
        raise ValueError("The XML law version does not match its pinned index")
    schedule = root.find(f'.//a:hcontainer[@eId="{manifest["schedule"]}"]', AKN)
    if schedule is None:
        raise ValueError("The Australian Consumer Law schedule is missing")
    schedule_heading = schedule.find("a:heading", AKN)
    if schedule_heading is None or "Australian Consumer Law" not in "".join(schedule_heading.itertext()):
        raise ValueError("Selected schedule is not the Australian Consumer Law")
    clauses = {}
    for element in schedule.findall('.//a:hcontainer[@name="clause"]', AKN):
        number = element.find("a:num", AKN)
        if number is not None:
            key = "".join(number.itertext()).strip()
            if key in clauses:
                raise ValueError(f"Duplicate statutory section: {key}")
            clauses[key] = element
    if len(manifest["sections"]) != len(set(manifest["sections"])):
        raise ValueError("The manifest contains duplicate sections")
    missing = set(manifest["sections"]) - set(clauses)
    if missing:
        raise ValueError(f"Missing selected sections: {sorted(missing)}")
    documents = []
    for number in manifest["sections"]:
        element = clauses[number]
        heading = element.find("a:heading", AKN)
        heading = " ".join("".join(heading.itertext()).split()) if heading is not None else ""
        text = " ".join("".join(element.itertext()).split())
        if not heading or len(text.split()) < 10:
            raise ValueError(f"Incomplete statutory section: {number}")
        documents.append({
            "id": f"acl-s{number.lower()}",
            "title": f"Australian Consumer Law — s {number}: {heading}",
            "law_title": metadata["name"], "law_id": metadata["title_id"],
            "section_number": number, "section_heading": heading,
            "url": f'https://www.legislation.gov.au/{metadata["title_id"]}/{metadata["effective_date"]}/text',
            "current_source_url": f'https://www.legislation.gov.au/{metadata["title_id"]}/latest/text',
            "publisher": "Commonwealth of Australia", "jurisdiction": "Commonwealth",
            "source_kind": "legislation_extract", "version_date": metadata["effective_date"],
            "compilation_id": metadata["comp_id"], "retrieved_at": retrieved_at,
            "dataset": manifest["dataset"], "dataset_revision": manifest["revision"],
            "dataset_url": f'https://huggingface.co/datasets/{manifest["dataset"]}',
            "dataset_file_url": f'https://huggingface.co/datasets/{manifest["dataset"]}/blob/{manifest["revision"]}/{manifest["xml_file"]}',
            "dataset_element_id": element.get("eId"),
            "source_sha256": manifest["xml_sha256"],
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "license": manifest["license"], "license_url": manifest["license_url"],
            "text": text,
        })
    return documents


def import_huggingface(manifest_path, output, cache):
    manifest = json.loads(Path(manifest_path).read_text())
    raw_index = download_file(manifest["dataset"], manifest["revision"], manifest["index_file"], manifest["index_sha256"], cache)
    raw_xml = download_file(manifest["dataset"], manifest["revision"], manifest["xml_file"], manifest["xml_sha256"], cache)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    documents = extract_sections(raw_xml, json.loads(raw_index), manifest, retrieved_at)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(doc, ensure_ascii=False) + "\n" for doc in documents))
    temporary.replace(output)
    return len(documents)
