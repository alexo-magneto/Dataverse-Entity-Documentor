"""Parse sitemap.sitemapxml into Area / Group / SubArea nodes."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class SiteMapNode:
    kind: str  # Area | Group | SubArea
    id: str
    title: str
    path: str
    entity: str = ""
    url: str = ""
    dashboard_id: str = ""
    web_resource: str = ""
    attributes: dict[str, str] = field(default_factory=dict)


def _title(el: ET.Element) -> str:
    if el.get("Title"):
        return el.get("Title", "")
    titles = el.find("Titles")
    if titles is not None:
        best = ""
        for t in titles.findall("Title"):
            if t.get("LCID") == "1033" and t.get("Title"):
                return t.get("Title", "")
            best = best or t.get("Title", "")
        if best:
            return best
    return el.get("ResourceId") or el.get("Id") or ""


def _node(kind: str, el: ET.Element, path: str) -> SiteMapNode:
    url = el.get("Url", "") or ""
    web_resource = ""
    if url.startswith("$webresource:"):
        web_resource = url[len("$webresource:"):]
    node = SiteMapNode(
        kind=kind,
        id=el.get("Id", "") or "",
        title=_title(el),
        path=path,
        entity=(el.get("Entity", "") or "").lower(),
        url=url,
        dashboard_id=(el.get("DefaultDashboard", "") or "").strip("{}").lower(),
        web_resource=web_resource,
        attributes={k: v for k, v in el.attrib.items()},
    )
    return node


def parse_sitemap_xml(xml: str) -> list[SiteMapNode]:
    nodes: list[SiteMapNode] = []
    if not xml or not xml.strip():
        return nodes
    root = ET.fromstring(xml.strip())
    for area in root.iter("Area"):
        area_node = _node("Area", area, _title(area))
        nodes.append(area_node)
        for group in area.findall("Group"):
            group_node = _node("Group", group, f"{area_node.title} / {_title(group)}")
            nodes.append(group_node)
            for sub in group.findall("SubArea"):
                nodes.append(_node("SubArea", sub, f"{group_node.path} / {_title(sub)}"))
        # Some sitemaps place SubAreas directly under an Area.
        for sub in area.findall("SubArea"):
            nodes.append(_node("SubArea", sub, f"{area_node.title} / {_title(sub)}"))
    return nodes
