"""Output row models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ComponentRow:
    component_name: str
    component_type: str
    logical_name: str = ""  # logical / unique name (or id when no name exists)
    parent_entity: str = ""
    component_id: str = ""
    discovery_source: str = ""
    details: str = ""

    def key(self) -> tuple[str, str, str, str]:
        return (self.component_type, self.logical_name or self.component_name, self.parent_entity, self.component_id)


@dataclass
class EntityRow:
    logical_name: str
    display_name: str
    discovery_sources: list[str] = field(default_factory=list)
    is_custom_entity: bool = False
    is_activity: bool = False
    schema_name: str = ""
    object_type_code: int | None = None
    depth: int = 0
    referenced_by: list[str] = field(default_factory=list)
    is_managed: bool = False

    @property
    def discovery_source(self) -> str:
        return self.discovery_sources[0] if self.discovery_sources else ""


@dataclass
class AppDocumentation:
    app_name: str
    app_unique_name: str
    app_id: str
    environment_url: str
    generated_at: str
    components: list[ComponentRow] = field(default_factory=list)
    entities: dict[str, EntityRow] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    _component_keys: set = field(default_factory=set, repr=False)

    def add_component(self, row: ComponentRow) -> bool:
        k = row.key()
        if k in self._component_keys:
            # Merge discovery sources for duplicates so nothing is lost.
            for existing in self.components:
                if existing.key() == k:
                    if row.discovery_source and row.discovery_source not in existing.discovery_source:
                        existing.discovery_source = f"{existing.discovery_source}; {row.discovery_source}".strip("; ")
                    if row.details and row.details not in existing.details:
                        existing.details = f"{existing.details} | {row.details}".strip(" |")
                    break
            return False
        self._component_keys.add(k)
        self.components.append(row)
        return True

    def counts_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.components:
            counts[c.component_type] = counts.get(c.component_type, 0) + 1
        return dict(sorted(counts.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "appName": self.app_name,
            "appUniqueName": self.app_unique_name,
            "appId": self.app_id,
            "environmentUrl": self.environment_url,
            "generatedAt": self.generated_at,
            "components": [asdict(c) for c in self.components],
            "entities": [asdict(e) for e in sorted(self.entities.values(), key=lambda e: (e.depth, e.logical_name))],
            "warnings": list(self.warnings),
        }
