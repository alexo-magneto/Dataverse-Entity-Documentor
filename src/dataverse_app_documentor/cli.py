"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .auth import build_token_provider
from .client import DataverseClient, DataverseError
from .config import load_config, validate_config
from .discovery import AppDocumenter
from .metadata import MetadataCache


def _safe_file_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "app"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dataverse-app-documentor",
        description="Document every component and entity used by a Dataverse model-driven app into Excel.",
    )
    p.add_argument("--config", "-c", help="Path to config.json (default: config.local.json, config.json, configf.json in cwd)")
    p.add_argument("--app", "-a", action="append", help="Model-driven app display name or unique name (repeatable). Overrides config apps.")
    p.add_argument("--list-apps", action="store_true", help="List model-driven apps in the environment and exit.")
    p.add_argument("--whoami", action="store_true", help="Test the connection (WhoAmI) and exit.")
    p.add_argument("--output-dir", "-o", help="Output directory (default from config: ./output)")
    p.add_argument("--output-file", help="Output file name (default from config).")
    p.add_argument("--depth", type=int, help="Traversal depth: 0 = sitemap/app components only, 1 = walk app entity forms (default), 2+ = also walk discovered entities.")
    p.add_argument("--attributes", choices=["form", "all", "none"], help="Attribute scope: fields on identified forms (default), all entity attributes, or none.")
    p.add_argument("--include-relationships", action="store_true", help="Also list every relationship of walked entities (can be large).")
    p.add_argument("--include-inactive-forms", action="store_true", help="Include inactive forms.")
    p.add_argument("--json", action="store_true", help="Also write a JSON file with the raw documentation model.")
    p.add_argument("--separate-workbooks", action="store_true", help="Write one workbook per app instead of one workbook with tabs per app.")
    p.add_argument("--verbose", "-v", action="count", default=0, help="-v for info, -vv for debug (includes every HTTP request).")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    level = logging.WARNING if args.verbose == 0 else logging.INFO if args.verbose == 1 else logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    if args.verbose < 2:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("msal").setLevel(logging.WARNING)
    # Always show progress lines from discovery unless the user asked for silence.
    logging.getLogger("dataverse_app_documentor.discovery").setLevel(min(level, logging.INFO))
    logging.getLogger("dataverse_app_documentor.metadata").setLevel(min(level, logging.INFO))

    try:
        cfg = load_config(args.config)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.depth is not None:
        cfg.discovery.traversal_depth = args.depth
    if args.attributes:
        cfg.discovery.attribute_scope = args.attributes
    if args.include_relationships:
        cfg.discovery.include_all_relationships = True
    if args.include_inactive_forms:
        cfg.discovery.include_inactive_forms = True
    if args.output_dir:
        cfg.output.directory = args.output_dir
    if args.output_file:
        cfg.output.file_name = args.output_file
    if args.json:
        cfg.output.write_json = True
    if args.separate_workbooks:
        cfg.output.single_workbook = False

    problems = validate_config(cfg)
    if problems:
        print("Configuration problems:", file=sys.stderr)
        for pr in problems:
            print(f"  - {pr}", file=sys.stderr)
        print(f"\nConfig file: {cfg.source_path or '(none found)'}", file=sys.stderr)
        return 2

    try:
        token_provider = build_token_provider(cfg.auth, cfg.environment_url)
        client = DataverseClient(cfg.environment_url, token_provider, api_version=cfg.api_version)
        meta = MetadataCache(client)
        documenter = AppDocumenter(client, meta, cfg.discovery)

        if args.whoami:
            who = client.who_am_i()
            print(json.dumps(who, indent=2))
            return 0

        if args.list_apps:
            apps = documenter.list_apps()
            print(f"{'Name':<50} {'Unique Name':<45} {'App Id'}")
            print("-" * 130)
            for a in apps:
                print(f"{(a.get('name') or ''):<50} {(a.get('uniquename') or ''):<45} {a.get('appmoduleid')}")
            print(f"\n{len(apps)} app(s).")
            return 0

        app_names = args.app or cfg.apps
        if not app_names:
            print("ERROR: no app specified. Use --app \"App Name\" or set \"apps\" in config.json (--list-apps shows names).", file=sys.stderr)
            return 2

        from .excel import write_workbook  # imported here so --list-apps works without openpyxl

        docs = []
        for name in app_names:
            docs.append(documenter.document_app(name))

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_dir = Path(cfg.output.directory)
        written: list[Path] = []

        def _name(app_label: str) -> str:
            return cfg.output.file_name.format(app=_safe_file_part(app_label), timestamp=timestamp)

        if cfg.output.single_workbook:
            label = docs[0].app_name if len(docs) == 1 else f"{len(docs)}-apps"
            written.append(write_workbook(docs, out_dir / _name(label)))
        else:
            for doc in docs:
                written.append(write_workbook([doc], out_dir / _name(doc.app_name)))

        if cfg.output.write_json:
            for doc in docs:
                jpath = out_dir / (Path(_name(doc.app_name)).stem + ".json")
                jpath.write_text(json.dumps(doc.to_dict(), indent=2), encoding="utf-8")
                written.append(jpath)

        for doc in docs:
            print(f"\n{doc.app_name}: {len(doc.components)} components, {len(doc.entities)} entities")
            for ctype, count in doc.counts_by_type().items():
                print(f"  {ctype:<45} {count:>6}")
            if doc.warnings:
                print(f"  {len(doc.warnings)} warning(s) - see Summary tab")
        print("\nWritten:")
        for w in written:
            print(f"  {w}")
        return 0

    except DataverseError as exc:
        print(f"\nDataverse error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
