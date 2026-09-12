"""Lazy, cached access to EntityDefinitions, attributes and relationships."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .client import DataverseClient, odata_quote

log = logging.getLogger(__name__)


def _label(node: Any) -> str:
    if not isinstance(node, dict):
        return ""
    ull = node.get("UserLocalizedLabel")
    if isinstance(ull, dict) and ull.get("Label"):
        return ull["Label"]
    for lbl in node.get("LocalizedLabels", []) or []:
        if lbl.get("Label"):
            return lbl["Label"]
    return ""


@dataclass
class EntityMeta:
    logical_name: str
    display_name: str
    schema_name: str
    entity_set_name: str
    metadata_id: str
    object_type_code: int | None
    is_custom: bool
    is_activity: bool
    has_activities: bool
    has_notes: bool
    primary_id_attribute: str
    primary_name_attribute: str
    is_managed: bool


@dataclass
class AttributeMeta:
    logical_name: str
    display_name: str
    schema_name: str
    attribute_type: str
    is_custom: bool
    targets: list[str] = field(default_factory=list)
    is_primary_id: bool = False


@dataclass
class RelationshipMeta:
    schema_name: str
    kind: str  # OneToMany | ManyToOne | ManyToMany
    referenced_entity: str
    referencing_entity: str
    referencing_attribute: str = ""
    entity1: str = ""
    entity2: str = ""
    intersect_entity: str = ""

    def other_entity(self, this_entity: str) -> str:
        if self.kind == "ManyToMany":
            return self.entity2 if self.entity1 == this_entity else self.entity1
        return self.referencing_entity if self.referenced_entity == this_entity else self.referenced_entity


ENTITY_SELECT = (
    "LogicalName,DisplayName,SchemaName,EntitySetName,MetadataId,ObjectTypeCode,IsCustomEntity,"
    "IsActivity,HasActivities,HasNotes,PrimaryIdAttribute,PrimaryNameAttribute,IsManaged"
)
ATTRIBUTE_SELECT = "LogicalName,DisplayName,SchemaName,AttributeType,IsCustomAttribute,MetadataId"


class MetadataCache:
    def __init__(self, client: DataverseClient) -> None:
        self.client = client
        self._entities: dict[str, EntityMeta] = {}
        self._by_metadata_id: dict[str, EntityMeta] = {}
        self._by_otc: dict[int, EntityMeta] = {}
        self._attributes: dict[str, dict[str, AttributeMeta]] = {}
        self._relationships: dict[str, list[RelationshipMeta]] = {}
        self._loaded = False

    # ------------------------------------------------------------- entities
    def load_entities(self) -> None:
        if self._loaded:
            return
        log.info("Loading entity metadata (EntityDefinitions)...")
        rows = self.client.get_all("EntityDefinitions", {"$select": ENTITY_SELECT})
        for row in rows:
            meta = EntityMeta(
                logical_name=row["LogicalName"],
                display_name=_label(row.get("DisplayName")) or row["LogicalName"],
                schema_name=row.get("SchemaName", ""),
                entity_set_name=row.get("EntitySetName", "") or "",
                metadata_id=(row.get("MetadataId") or "").lower(),
                object_type_code=row.get("ObjectTypeCode"),
                is_custom=bool(row.get("IsCustomEntity")),
                is_activity=bool(row.get("IsActivity")),
                has_activities=bool(row.get("HasActivities")),
                has_notes=bool(row.get("HasNotes")),
                primary_id_attribute=row.get("PrimaryIdAttribute", "") or "",
                primary_name_attribute=row.get("PrimaryNameAttribute", "") or "",
                is_managed=bool(row.get("IsManaged")),
            )
            self._entities[meta.logical_name] = meta
            if meta.metadata_id:
                self._by_metadata_id[meta.metadata_id] = meta
            if meta.object_type_code is not None:
                self._by_otc[meta.object_type_code] = meta
        self._loaded = True
        log.info("Loaded %s entities", len(self._entities))

    def all_entities(self) -> list[EntityMeta]:
        self.load_entities()
        return list(self._entities.values())

    def entity(self, logical_name: str) -> EntityMeta | None:
        self.load_entities()
        return self._entities.get((logical_name or "").lower())

    def entity_by_metadata_id(self, metadata_id: str) -> EntityMeta | None:
        self.load_entities()
        return self._by_metadata_id.get((metadata_id or "").lower().strip("{}"))

    def entity_by_object_type_code(self, otc: int | str) -> EntityMeta | None:
        self.load_entities()
        try:
            return self._by_otc.get(int(otc))
        except (TypeError, ValueError):
            return None

    def resolve_entity(self, ref: str) -> EntityMeta | None:
        """Resolve by logical name, object type code, or metadata id."""
        if ref is None:
            return None
        ref = str(ref).strip()
        if not ref:
            return None
        if ref.isdigit():
            return self.entity_by_object_type_code(ref)
        if len(ref.strip("{}")) == 36 and "-" in ref:
            return self.entity_by_metadata_id(ref)
        return self.entity(ref)

    def activity_entities(self) -> list[EntityMeta]:
        return [e for e in self.all_entities() if e.is_activity]

    # ----------------------------------------------------------- attributes
    def attributes(self, logical_name: str) -> dict[str, AttributeMeta]:
        logical_name = logical_name.lower()
        if logical_name in self._attributes:
            return self._attributes[logical_name]
        ent = self.entity(logical_name)
        result: dict[str, AttributeMeta] = {}
        if ent is None:
            self._attributes[logical_name] = result
            return result
        log.debug("Loading attributes for %s", logical_name)
        path = f"EntityDefinitions(LogicalName={odata_quote(logical_name)})/Attributes"
        for row in self.client.get_all(path, {"$select": ATTRIBUTE_SELECT}):
            result[row["LogicalName"]] = AttributeMeta(
                logical_name=row["LogicalName"],
                display_name=_label(row.get("DisplayName")) or row["LogicalName"],
                schema_name=row.get("SchemaName", ""),
                attribute_type=row.get("AttributeType", "") or "",
                is_custom=bool(row.get("IsCustomAttribute")),
                is_primary_id=row["LogicalName"] == ent.primary_id_attribute,
            )
        # Lookup targets are only exposed on the LookupAttributeMetadata subtype.
        lookup_path = path + "/Microsoft.Dynamics.CRM.LookupAttributeMetadata"
        try:
            for row in self.client.get_all(lookup_path, {"$select": "LogicalName,Targets"}):
                attr = result.get(row["LogicalName"])
                if attr is not None:
                    attr.targets = list(row.get("Targets") or [])
        except Exception as exc:  # metadata subtype query not available - degrade gracefully
            log.warning("Could not load lookup targets for %s: %s", logical_name, exc)
        self._attributes[logical_name] = result
        return result

    # -------------------------------------------------------- relationships
    def relationships(self, logical_name: str) -> list[RelationshipMeta]:
        logical_name = logical_name.lower()
        if logical_name in self._relationships:
            return self._relationships[logical_name]
        rels: list[RelationshipMeta] = []
        if self.entity(logical_name) is None:
            self._relationships[logical_name] = rels
            return rels
        log.debug("Loading relationships for %s", logical_name)
        path = f"EntityDefinitions(LogicalName={odata_quote(logical_name)})"
        expand = (
            "OneToManyRelationships($select=SchemaName,ReferencedEntity,ReferencingEntity,ReferencingAttribute),"
            "ManyToOneRelationships($select=SchemaName,ReferencedEntity,ReferencingEntity,ReferencingAttribute),"
            "ManyToManyRelationships($select=SchemaName,Entity1LogicalName,Entity2LogicalName,IntersectEntityName)"
        )
        try:
            data = self.client.get(path, {"$select": "LogicalName", "$expand": expand})
        except Exception:
            data = self.client.get(
                path,
                {"$select": "LogicalName", "$expand": "OneToManyRelationships,ManyToOneRelationships,ManyToManyRelationships"},
            )
        for row in data.get("OneToManyRelationships", []) or []:
            rels.append(RelationshipMeta(row["SchemaName"], "OneToMany", row["ReferencedEntity"], row["ReferencingEntity"], row.get("ReferencingAttribute", "")))
        for row in data.get("ManyToOneRelationships", []) or []:
            rels.append(RelationshipMeta(row["SchemaName"], "ManyToOne", row["ReferencedEntity"], row["ReferencingEntity"], row.get("ReferencingAttribute", "")))
        for row in data.get("ManyToManyRelationships", []) or []:
            rels.append(RelationshipMeta(row["SchemaName"], "ManyToMany", "", "", "", row["Entity1LogicalName"], row["Entity2LogicalName"], row.get("IntersectEntityName", "")))
        self._relationships[logical_name] = rels
        return rels

    def relationship_by_name(self, logical_name: str, schema_name: str) -> RelationshipMeta | None:
        target = (schema_name or "").lower()
        for rel in self.relationships(logical_name):
            if rel.schema_name.lower() == target:
                return rel
        return None
