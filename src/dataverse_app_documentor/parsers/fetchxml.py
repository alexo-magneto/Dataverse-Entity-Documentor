"""FetchXML / layoutxml helpers for views and charts."""

from __future__ import annotations

import xml.etree.ElementTree as ET


def parse_fetch_entities(fetchxml: str) -> tuple[str, list[str]]:
    """Return (primary entity, [linked entities]) from a FetchXML string."""
    if not fetchxml or not fetchxml.strip():
        return "", []
    try:
        root = ET.fromstring(fetchxml.strip())
    except ET.ParseError:
        return "", []
    entity = root.find("entity")
    if entity is None:  # chart datadescription wraps fetch inside <datadefinition><fetchcollection>
        entity = next(root.iter("entity"), None)
    primary = (entity.get("name", "") if entity is not None else "").lower()
    linked: list[str] = []
    for link in root.iter("link-entity"):
        name = (link.get("name") or "").lower()
        if name and name not in linked:
            linked.append(name)
    return primary, linked


def parse_layout_columns(layoutxml: str) -> list[str]:
    if not layoutxml or not layoutxml.strip():
        return []
    try:
        root = ET.fromstring(layoutxml.strip())
    except ET.ParseError:
        return []
    cols: list[str] = []
    for cell in root.iter("cell"):
        name = cell.get("name")
        if name and name not in cols:
            cols.append(name)
    return cols
