"""Reads a person's intake.json (their answers to the setup questions) and turns
it into config overrides plus template context for generate_project.py.

Validation runs against ../intake.schema.json itself, so the schema file is the
single source of truth. Only the small subset of JSON Schema that file uses is
supported: type, const, enum, required, properties, items, minItems, maxItems,
uniqueItems, minLength, maxLength, pattern, format "date". "title",
"description" and "x-labels" are the page's wording; the templates use the
labels too. Unknown fields are reported as warnings, never
errors, so a newer setup page doesn't break an older generator.

Free text is never rewritten here: it is passed to the templates exactly as
the person typed it.
"""
import datetime
import json
import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "intake.schema.json"

TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "integer": int,
}

# Where each intake answer goes in the generator config (B18 in the plan).
SOURCE_MAP = {
    "company_boards": ["greenhouse", "ashby"],
    "yc": ["yc"],
    "hn": ["hn"],
    "web": ["web"],
}
DRAFTS_MAP = {
    "none": ("none", False),
    "strong": ("strong", False),
    "strong_with_outreach": ("strong", True),
    "all": ("all", False),
}
SECTIONS = ("basics", "what_you_want", "work_authorization", "risk", "where_to_look", "job_finder", "about_you")


class IntakeError(ValueError):
    """The intake file can't be used. The message lists every problem."""


def _check(value, schema, path, errors, warnings):
    where = path or "(top level)"
    if "const" in schema and value != schema["const"]:
        errors.append(f"{where}: must be {schema['const']!r}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: {value!r} is not one of {schema['enum']}")
        return
    expected = schema.get("type")
    if expected:
        ok = isinstance(value, TYPES[expected])
        if expected == "integer" and isinstance(value, bool):
            ok = False
        if not ok:
            errors.append(f"{where}: should be {'an' if expected[0] in 'aeiou' else 'a'} {expected}")
            return
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path + '.' if path else ''}{key}: is required")
        for key, sub in value.items():
            sub_path = f"{path}.{key}" if path else key
            if key in props:
                _check(sub, props[key], sub_path, errors, warnings)
            else:
                warnings.append(f"{sub_path}: unknown field, ignored")
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{where}: needs at least {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{where}: at most {schema['maxItems']} allowed, got {len(value)}")
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            errors.append(f"{where}: has the same choice more than once")
        if "items" in schema:
            for i, item in enumerate(value):
                _check(item, schema["items"], f"{path}[{i}]", errors, warnings)
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where}: can't be empty")
        elif "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where}: can't be blank" if schema["pattern"] == "\\S" else f"{where}: {value!r} isn't in the expected format")
        if schema.get("format") == "date":
            try:
                datetime.date.fromisoformat(value)
            except ValueError:
                errors.append(f"{where}: should be a date like 2027-03-31")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{where}: too long ({len(value)} characters, limit {schema['maxLength']})")


def validate(intake) -> list:
    """Returns warnings. Raises IntakeError listing every problem found."""
    schema = json.loads(SCHEMA_PATH.read_text())
    errors, warnings = [], []
    _check(intake, schema, "", errors, warnings)
    if errors:
        raise IntakeError("intake.json has problems:\n  - " + "\n  - ".join(errors + warnings))
    return warnings


def labels() -> dict:
    """Every "x-labels" map in the schema, keyed by field name (e.g.
    labels()["priorities"]["pay"] == "Pay"). Field names are unique enough in
    this schema for that to be unambiguous."""
    found = {}

    def walk(node, name=None):
        if isinstance(node, dict):
            if "x-labels" in node and name:
                found[name] = node["x-labels"]
            for key, sub in node.items():
                if key == "properties":
                    for prop, prop_schema in sub.items():
                        walk(prop_schema, prop)
                elif key == "items":
                    walk(sub, name)
    walk(json.loads(SCHEMA_PATH.read_text()))
    return found


def load(path) -> tuple:
    """Reads and validates an intake file. Returns (intake, warnings)."""
    try:
        intake = json.loads(Path(path).read_text())
    except json.JSONDecodeError as e:
        raise IntakeError(f"intake.json isn't valid JSON: {e}")
    return intake, validate(intake)


def _db_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:30] or "me"


def apply(cfg: dict, intake: dict) -> tuple:
    """Merges intake answers over a job-search config. Returns (cfg, warnings).

    The result still goes through generate_project.apply_defaults, which
    validates it like any other config."""
    cfg = dict(cfg)
    warnings = []
    intake = {**{s: {} for s in SECTIONS}, "stories": [], **intake}
    basics, finder = intake["basics"], intake["job_finder"]
    name = basics["preferred_name"].strip()

    cfg["app_display_name"] = f"{name}'s Job Search"
    cfg["user_initial"] = name[:1].upper()
    cfg["db_name"] = "job_search_" + _db_slug(name)

    finder_on = basics.get("job_finder", True)
    drafting_on = basics.get("drafting", True)
    if drafting_on and not finder_on:
        warnings.append("basics.drafting: cover-letter drafting needs the job finder in this version, so it is off")
        drafting_on = False

    cfg["has_coaching"] = True  # the intake questions are the coaching's starting point
    cfg["has_scout_agent"] = finder_on
    if not finder_on:
        queued = cfg.get("queued_stage")
        cfg["stages"] = [s for s in cfg["stages"] if s != queued]
        cfg.pop("queued_stage", None)
        cfg["artifact_enabled"] = False
        for key in ("artifact_scope", "scout_outreach_mode"):
            cfg.pop(key, None)
    else:
        cfg["artifact_enabled"] = drafting_on
        if "sources" in finder:
            if not finder["sources"]:
                raise IntakeError("intake.json has problems:\n  - job_finder.sources: choose at least one place to look, or turn the job finder off")
            cfg["scout_sources"] = [s for key in finder["sources"] for s in SOURCE_MAP[key]]
        if "run_size" in finder:
            cfg["scout_budget_preset"] = finder["run_size"]
        if "pickiness" in finder:
            cfg["scout_tier_mode"] = finder["pickiness"]
        if drafting_on:
            scope, outreach = DRAFTS_MAP[finder.get("drafts", "strong")]
        else:
            scope, outreach = "none", False
        cfg["artifact_scope"] = scope
        cfg["scout_outreach_mode"] = outreach
        cfg["watch_companies"] = [w.strip() for w in finder.get("watch_companies", [])]
        if "daily_run" in finder:
            cfg["daily_run"] = finder["daily_run"]

    cfg["intake"] = intake
    cfg["intake_labels"] = labels()
    cfg["person_name"] = name
    return cfg, warnings
