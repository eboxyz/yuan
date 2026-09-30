"""Renders the tracker-setup templates into a new project directory.

Usage:
    python3 generate_project.py <config.json> <target_dir>
        [--intake intake.json] [--db-name NAME] [--port N] [--zip]

Reads a config describing one domain (entity names, stages, which optional
axes are enabled), renders every template in ../templates/ with that config,
and writes the result into <target_dir>, mirroring the layout of the
original job search tracker project.

--intake   a person's answers to the setup questions (see intake.schema.json);
           merged over the config, and their words go into the settings files
--db-name, --port   override everything else (used for sandboxes)
--zip      also write <target_dir>.zip, ready to send to the person
"""
import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import intake as intake_mod

SKILL_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = SKILL_DIR / "templates"

# (bg, text) Tailwind class pairs, reused from the original hand-authored
# STAGE_CHIP map. Cycled across stages by role so every generated project
# gets a coherent, non-clashing set of chip colors without hand-authoring
# one pair per literal stage name.
QUEUED_PAIR = ("bg-secondary-container", "text-on-secondary-container")
BASELINE_PAIR = ("bg-primary-container", "text-on-primary-container")
SUCCESS_PAIR = ("bg-tertiary-fixed-dim", "text-on-tertiary-fixed")
IN_PROGRESS_PAIRS = [
    ("bg-secondary-container", "text-on-secondary-container"),
    ("bg-tertiary-container", "text-on-tertiary-container"),
]
CLOSED_PAIRS = [
    ("bg-surface-container-highest", "text-on-surface-variant"),
    ("bg-surface-variant", "text-on-surface-variant"),
]


# Scout options. The four job sources ship with ready-made tools (see
# templates/skills/scout_agent/tools); "web" means plain web search.
JOB_SOURCES = ("greenhouse", "ashby", "yc", "hn")
SCOUT_SOURCES = JOB_SOURCES + ("web",)
BUDGET_PRESETS = {
    "light": {"scout_candidates_target": 5, "scout_candidates_cap": 8, "scout_jd_fetch_cap": 12, "scout_terms_per_run": 4},
    "standard": {"scout_candidates_target": 10, "scout_candidates_cap": 15, "scout_jd_fetch_cap": 25, "scout_terms_per_run": 8},
    "thorough": {"scout_candidates_target": 15, "scout_candidates_cap": 25, "scout_jd_fetch_cap": 50, "scout_terms_per_run": "all"},
}
TIER_MODES = ("strong_only", "strong_and_maybe")
ARTIFACT_SCOPES = ("none", "strong", "all")


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "project"


class ConfigError(ValueError):
    """Raised when config.json is missing or self-inconsistent. Caught in
    __main__ and printed as a plain message — no one hand-filling this
    config by hand (or steering an agent through it) should ever see a
    Python traceback for a mistake this checkable."""


def validate_config(cfg: dict) -> None:
    errors = []

    def require(key, label=None):
        if not cfg.get(key):
            errors.append(f"missing required field: {label or key}")

    for key in (
        "project_name",
        "entity_singular",
        "entity_plural",
        "primary_field",
        "secondary_field",
        "stages",
        "baseline_stage",
        "success_stage",
        "closed_stages",
    ):
        require(key)

    if errors:
        # Everything below assumes these are present — report what's missing
        # first rather than piling on confusing follow-on errors.
        raise ConfigError(
            "config.json is missing required fields:\n  - " + "\n  - ".join(errors)
        )

    stages = cfg["stages"]
    if not isinstance(stages, list) or not stages:
        errors.append("stages must be a non-empty list")
    elif len(stages) != len(set(stages)):
        errors.append("stages has duplicate entries")

    if cfg.get("entity_singular") == cfg.get("entity_plural"):
        errors.append("entity_singular and entity_plural must be different")

    if isinstance(stages, list) and stages:
        for label in ("baseline_stage", "success_stage"):
            if cfg[label] not in stages:
                errors.append(f"{label} ({cfg[label]!r}) is not in stages {stages}")

        closed = cfg["closed_stages"]
        if not isinstance(closed, list) or not closed:
            errors.append("closed_stages must be a non-empty list")
        else:
            for stage in closed:
                if stage not in stages:
                    errors.append(f"closed_stages entry {stage!r} is not in stages {stages}")

        if cfg.get("has_scout_agent"):
            queued = cfg.get("queued_stage")
            if not queued:
                errors.append("has_scout_agent is true but queued_stage is missing")
            elif queued not in stages:
                errors.append(f"queued_stage ({queued!r}) is not in stages {stages}")

    if cfg.get("has_scout_agent"):
        errors.extend(validate_scout_options(cfg))

    if errors:
        raise ConfigError("config.json has problems:\n  - " + "\n  - ".join(errors))


def validate_scout_options(cfg: dict) -> list:
    errors = []
    sources = cfg.get("scout_sources", ["web"])
    if not isinstance(sources, list) or not sources:
        errors.append("scout_sources must be a non-empty list, e.g. [\"web\"]")
    else:
        bad = [x for x in sources if x not in SCOUT_SOURCES]
        if bad:
            errors.append(f"scout_sources has unknown value(s) {bad}; choose from {list(SCOUT_SOURCES)}")
        if len(set(sources)) != len(sources):
            errors.append("scout_sources has duplicate entries")
    preset = cfg.get("scout_budget_preset", "standard")
    if preset not in BUDGET_PRESETS:
        errors.append(f"scout_budget_preset {preset!r} is not one of {list(BUDGET_PRESETS)}")
    tier = cfg.get("scout_tier_mode", "strong_and_maybe")
    if tier not in TIER_MODES:
        errors.append(f"scout_tier_mode {tier!r} is not one of {list(TIER_MODES)}")
    scope = cfg.get("artifact_scope")
    if scope is not None:
        if scope not in ARTIFACT_SCOPES:
            errors.append(f"artifact_scope {scope!r} is not one of {list(ARTIFACT_SCOPES)}")
        elif scope != "none" and not cfg.get("artifact_enabled"):
            errors.append(f"artifact_scope {scope!r} needs artifact_enabled to be true")
    watch = cfg.get("watch_companies", [])
    if not isinstance(watch, list) or not all(isinstance(w, str) and w.strip() and len(w) <= 100 for w in watch):
        errors.append("watch_companies must be a list of non-empty names (each up to 100 characters)")
    elif len(watch) > 50:
        errors.append("watch_companies has more than 50 entries")
    daily = cfg.get("daily_run", "off")
    if daily != "off" and not (isinstance(daily, str) and re.fullmatch(r"([01]?[0-9]|2[0-3]):[0-5][0-9]", daily)):
        errors.append(f"daily_run {daily!r} must be \"off\" or a 24-hour time like \"08:00\"")
    outreach = cfg.get("scout_outreach_mode", False)
    if not isinstance(outreach, bool):
        errors.append("scout_outreach_mode must be true or false")
    elif outreach and not cfg.get("artifact_enabled"):
        errors.append("scout_outreach_mode needs artifact_enabled to be true (it changes what gets drafted)")
    return errors


def apply_defaults(cfg: dict) -> dict:
    validate_config(cfg)
    cfg = dict(cfg)
    cfg.setdefault("project_slug", slugify(cfg["project_name"]))
    cfg.setdefault("app_display_name", cfg["project_name"])
    cfg.setdefault("tagline", "Keep going!")
    cfg.setdefault("icon", "work")
    cfg.setdefault("user_initial", cfg["app_display_name"][:1].upper() or "U")
    cfg.setdefault(
        "entity_plural_label", cfg["entity_plural"].replace("_", " ").title()
    )
    cfg.setdefault("primary_label", cfg["primary_field"].replace("_", " ").title())
    cfg.setdefault(
        "secondary_label", cfg["secondary_field"].replace("_", " ").title()
    )
    cfg.setdefault("source_type_options", ["Self-sourced", "Inbound"])

    cfg.setdefault("has_value", False)
    cfg.setdefault("has_category", False)
    cfg.setdefault("has_contact", False)
    cfg.setdefault("has_scout_agent", False)

    if cfg["has_value"]:
        cfg.setdefault("value_label", "Value")
        cfg.setdefault("value_field_prefix", slugify(cfg["value_label"]).replace("-", "_"))

    if cfg["has_category"]:
        cfg.setdefault("category_label", "Category")
        cfg.setdefault(
            "category_field", slugify(cfg["category_label"]).replace("-", "_")
        )

    if cfg["has_contact"]:
        cfg.setdefault("contact_singular", "contact")
        cfg.setdefault("contact_plural", cfg["contact_singular"] + "s")
        cfg.setdefault("contact_org_label", "Organization")
        cfg.setdefault(
            "contact_org_field", slugify(cfg["contact_org_label"]).replace("-", "_")
        )

    if cfg["has_scout_agent"]:
        cfg.setdefault("source_label", "source")
        cfg.setdefault("artifact_enabled", False)
        if cfg["artifact_enabled"]:
            cfg.setdefault("artifact_label", "Draft")
            cfg.setdefault(
                "artifact_field_prefix", slugify(cfg["artifact_label"]).replace("-", "_")
            )
            cfg.setdefault("artifact_slug", slugify(cfg["artifact_label"]))
            cfg.setdefault("artifact_dir_name", cfg["artifact_slug"].replace("-", "_") + "s")

        # Budget defaults keep a scheduled/repeated scout run's cost
        # predictable regardless of domain. A preset supplies the numbers;
        # any explicit scout_* key in the config wins over the preset.
        cfg.setdefault("scout_budget_preset", "standard")
        for key, value in BUDGET_PRESETS[cfg["scout_budget_preset"]].items():
            cfg.setdefault(key, value)
        cfg.setdefault("scout_subagents_per_run", 1)
        cfg.setdefault("scout_sources_per_run", "all")  # retired: every enabled source runs every time
        cfg.setdefault("scout_sources", ["web"])
        cfg.setdefault("scout_tier_mode", "strong_and_maybe")
        cfg.setdefault("watch_companies", [])
        cfg["watch_companies"] = [w.strip() for w in cfg["watch_companies"]]
        cfg.setdefault("scout_outreach_mode", False)
        cfg.setdefault("artifact_scope", "strong" if cfg["artifact_enabled"] else "none")
        cfg["job_sources"] = [x for x in cfg["scout_sources"] if x in JOB_SOURCES]
        cfg["uses_boards"] = any(x in cfg["scout_sources"] for x in ("greenhouse", "ashby"))
        # Daily scheduled run (installed with the person's OK in the first run).
        cfg.setdefault("daily_run", "off")
        cfg.setdefault("skip_if_waiting", 15)
        cfg["daily_run_tools"] = (["boards.py"] if cfg["uses_boards"] else []) + [
            f"{x}.py" for x in ("hn", "yc") if x in cfg["scout_sources"]]
    else:
        cfg["artifact_enabled"] = False
        cfg["job_sources"] = []
        cfg["uses_boards"] = False

    cfg.setdefault("intake", None)
    cfg.setdefault("person_name", None)
    cfg.setdefault("stage_notes", {})
    # Coaching (job search): the search-coach skill, criteria-first questions,
    # reflections.md and the session-start check-in hook.
    cfg.setdefault("has_coaching", False)
    if cfg["has_coaching"]:
        cfg.setdefault("intake_labels", intake_mod.labels())

    cfg.setdefault("config_dir_name", cfg["project_slug"].replace("-", "_"))
    cfg.setdefault("db_name", cfg["project_slug"].replace("-", "_") + "_tracker")
    cfg.setdefault("port", 8420)

    # Stage classification (queued_stage/baseline_stage/success_stage/
    # closed_stages presence and membership already checked in validate_config)
    stages = cfg["stages"]
    if not cfg["has_scout_agent"]:
        cfg["queued_stage"] = None
    classified = {cfg.get("queued_stage"), cfg["baseline_stage"], cfg["success_stage"]}
    classified |= set(cfg["closed_stages"])
    cfg["in_progress_stages"] = [s for s in stages if s not in classified]

    return cfg


def build_stage_chip(cfg: dict) -> dict:
    chip = {}
    if cfg.get("queued_stage"):
        bg, text = QUEUED_PAIR
        chip[cfg["queued_stage"]] = {"bg": bg, "text": text, "label": cfg["queued_stage"]}
    bg, text = BASELINE_PAIR
    chip[cfg["baseline_stage"]] = {"bg": bg, "text": text, "label": cfg["baseline_stage"]}
    for i, stage in enumerate(cfg["in_progress_stages"]):
        bg, text = IN_PROGRESS_PAIRS[i % len(IN_PROGRESS_PAIRS)]
        chip[stage] = {"bg": bg, "text": text, "label": stage}
    bg, text = SUCCESS_PAIR
    chip[cfg["success_stage"]] = {"bg": bg, "text": text, "label": cfg["success_stage"]}
    for i, stage in enumerate(cfg["closed_stages"]):
        bg, text = CLOSED_PAIRS[i % len(CLOSED_PAIRS)]
        chip[stage] = {"bg": bg, "text": text, "label": stage}
    return chip


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["tojson"] = json.dumps
    env.filters["sqlstr"] = lambda s: "'" + str(s).replace("'", "''") + "'"
    return env


# (template path relative to templates/, output path relative to target dir,
# a predicate on cfg deciding whether to render it at all)
FILES = [
    ("db/schema.sql.j2", "db/schema.sql", lambda c: True),
    ("api/server.py.j2", "api/server.py", lambda c: True),
    ("dashboard/app.js.j2", "dashboard/app.js", lambda c: True),
    ("dashboard/index.html.j2", "dashboard/index.html", lambda c: True),
    (
        "dashboard/entities.html.j2",
        lambda c: f"dashboard/{c['entity_plural']}.html",
        lambda c: True,
    ),
    ("dashboard/upcoming.html.j2", "dashboard/upcoming.html", lambda c: True),
    ("dashboard/value.html.j2", "dashboard/value.html", lambda c: c["has_value"]),
    ("dashboard/queue.html.j2", "dashboard/queue.html", lambda c: c["has_scout_agent"]),
    (
        "skills/insights/SKILL.md.j2",
        lambda c: f".claude/skills/{c['entity_singular']}-insights/SKILL.md",
        lambda c: True,
    ),
    (
        "skills/scout_agent/SKILL.md.j2",
        lambda c: f".claude/skills/{c['entity_singular']}-scout-agent/SKILL.md",
        lambda c: c["has_scout_agent"],
    ),
    (
        "config/criteria.md.j2",
        lambda c: f"{c['config_dir_name']}/criteria.md",
        lambda c: c["has_scout_agent"] or c["has_coaching"],
    ),
    (
        "config/search_terms.md.j2",
        lambda c: f"{c['config_dir_name']}/search_terms.md",
        lambda c: c["has_scout_agent"],
    ),
    (
        "config/profile.md.j2",
        lambda c: f"{c['config_dir_name']}/profile.md",
        lambda c: c["has_scout_agent"] and c["artifact_enabled"],
    ),
    (
        "config/voice.md.j2",
        lambda c: f"{c['config_dir_name']}/voice.md",
        lambda c: c["has_scout_agent"] and c["artifact_enabled"],
    ),
    (
        "config/rotation_state.json.j2",
        lambda c: f"{c['config_dir_name']}/rotation_state.json",
        lambda c: c["has_scout_agent"],
    ),
    (
        "config/overflow_backlog.jsonl.j2",
        lambda c: f"{c['config_dir_name']}/overflow_backlog.jsonl",
        lambda c: c["has_scout_agent"],
    ),
    (
        "config/reviewed_postings.jsonl.j2",
        lambda c: f"{c['config_dir_name']}/reviewed_postings.jsonl",
        lambda c: c["has_scout_agent"],
    ),
    (
        "config/proof_bank.md.j2",
        lambda c: f"{c['config_dir_name']}/proof_bank.md",
        lambda c: c["has_scout_agent"] and c["artifact_enabled"],
    ),
    (
        "skills/artifact_drafter/SKILL.md.j2",
        lambda c: f".claude/skills/{c['artifact_slug']}/SKILL.md",
        lambda c: c["has_scout_agent"] and c["artifact_enabled"],
    ),
    (
        "skills/proof_bank_builder/SKILL.md.j2",
        lambda c: ".claude/skills/proof-bank-builder/SKILL.md",
        lambda c: c["has_scout_agent"] and c["artifact_enabled"],
    ),
    (
        "config/watch_companies.txt.j2",
        lambda c: f"{c['config_dir_name']}/watch_companies.txt",
        lambda c: c["uses_boards"],
    ),
    (
        "config/known_boards.json.j2",
        lambda c: f"{c['config_dir_name']}/known_boards.json",
        lambda c: c["uses_boards"],
    ),
    (
        "skills/scout_agent/tools/tools.json.j2",
        lambda c: f".claude/skills/{c['entity_singular']}-scout-agent/tools/tools.json",
        lambda c: bool(c["job_sources"]),
    ),
    ("start.sh.j2", "start.sh", lambda c: True),
    ("README.md.j2", "README.md", lambda c: True),
    ("CLAUDE.md.j2", "CLAUDE.md", lambda c: True),
    ("schedule/run_daily.sh.j2", "run_daily.sh", lambda c: c["has_scout_agent"]),
    ("schedule/schedule.sh.j2", "schedule.sh", lambda c: c["has_scout_agent"]),
    ("skills/search_coach/SKILL.md.j2", ".claude/skills/search-coach/SKILL.md", lambda c: c["has_coaching"]),
    ("skills/resume_builder/SKILL.md.j2", ".claude/skills/resume-builder/SKILL.md", lambda c: c["has_coaching"] and c["artifact_enabled"]),
    (
        "config/reflections.md.j2",
        lambda c: f"{c['config_dir_name']}/reflections.md",
        lambda c: c["has_coaching"],
    ),
    ("hooks/settings.json.j2", ".claude/settings.json", lambda c: c["has_coaching"]),
    ("hooks/checkin.json.j2", ".claude/hooks/checkin.json", lambda c: c["has_coaching"]),
]


# Plain files copied as-is (not rendered): the scout's fetch tools, each only
# when a source that needs it is enabled, and the check-in hook script.
TOOLS_OUT = lambda c: f".claude/skills/{c['entity_singular']}-scout-agent/tools"
STATIC_FILES = [
    ("skills/scout_agent/tools/common.py", lambda c: f"{TOOLS_OUT(c)}/common.py", lambda c: bool(c["job_sources"])),
    ("skills/scout_agent/tools/boards.py", lambda c: f"{TOOLS_OUT(c)}/boards.py", lambda c: c["uses_boards"]),
    ("skills/scout_agent/tools/hn.py", lambda c: f"{TOOLS_OUT(c)}/hn.py", lambda c: "hn" in c["job_sources"]),
    ("skills/scout_agent/tools/yc.py", lambda c: f"{TOOLS_OUT(c)}/yc.py", lambda c: "yc" in c["job_sources"]),
    ("hooks/checkin.py", lambda c: ".claude/hooks/checkin.py", lambda c: c["has_coaching"]),
    # The dashboard's styles, fonts and icons, so it loads nothing from outside (dev/dashboard-css builds them).
    *[(f"dashboard/static/{p.relative_to(TEMPLATES_DIR / 'dashboard/static').as_posix()}",
       (lambda rel: lambda c: f"dashboard/{rel}")(p.relative_to(TEMPLATES_DIR / "dashboard/static").as_posix()), lambda c: True)
      for p in sorted((TEMPLATES_DIR / "dashboard/static").rglob("*")) if p.is_file()],
    ("skills/resume_builder/phrasing_guide.md", lambda c: ".claude/skills/resume-builder/phrasing_guide.md", lambda c: c["has_coaching"] and c["artifact_enabled"]),
    ("skills/resume_builder/resume_template.html", lambda c: ".claude/skills/resume-builder/resume_template.html", lambda c: c["has_coaching"] and c["artifact_enabled"]),
    ("skills/resume_builder/render_pdf.sh", lambda c: ".claude/skills/resume-builder/render_pdf.sh", lambda c: c["has_coaching"] and c["artifact_enabled"]),
]


# Left out of a --zip package: rebuilt on the person's machine, or noise.
ZIP_SKIP_DIRS = {".venv", "__pycache__"}
ZIP_SKIP_FILES = {".DS_Store", ".first_run_done"}

DB_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def write_zip(target: Path) -> Path:
    zip_path = target.with_name(target.name + ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(target.rglob("*")):
            rel = path.relative_to(target)
            if path.is_dir() or ZIP_SKIP_DIRS & set(rel.parts) or path.name in ZIP_SKIP_FILES:
                continue
            # zf.write keeps each file's mode, so start.sh and the tools stay executable.
            zf.write(path, Path(target.name) / rel)
    return zip_path


def generate(config_path: str, target_dir: str, intake_path=None, db_name=None, port=None, make_zip=False):
    cfg = json.loads(Path(config_path).read_text())
    intake = None
    if intake_path:
        intake, warnings = intake_mod.load(intake_path)
        cfg, more = intake_mod.apply(cfg, intake)
        for w in warnings + more:
            print(f"warning: {w}", file=sys.stderr)
    if db_name is not None:
        if not DB_NAME_RE.match(db_name):
            raise ConfigError("--db-name must be lowercase letters, digits and underscores, starting with a letter")
        cfg["db_name"] = db_name
    if port is not None:
        cfg["port"] = port
    cfg = apply_defaults(cfg)
    cfg["stage_chip_json"] = json.dumps(build_stage_chip(cfg))

    env = make_env()
    target = Path(target_dir)
    written = []
    for template_name, out_name, predicate in FILES:
        if not predicate(cfg):
            continue
        out_rel = out_name(cfg) if callable(out_name) else out_name
        out_path = target / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        template = env.get_template(template_name)
        out_path.write_text(template.render(**cfg))
        if out_path.suffix == ".sh":
            out_path.chmod(0o755)
        written.append(out_rel)

    for src_name, out_name, predicate in STATIC_FILES:
        if not predicate(cfg):
            continue
        out_rel = out_name(cfg)
        out_path = target / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATES_DIR / src_name, out_path)
        if out_path.suffix in (".py", ".sh"):
            out_path.chmod(0o755)
        written.append(out_rel)

    if intake is not None:
        out_rel = f"{cfg['config_dir_name']}/intake.json"
        (target / out_rel).parent.mkdir(parents=True, exist_ok=True)
        (target / out_rel).write_text(json.dumps(intake, indent=2, ensure_ascii=False) + "\n")
        written.append(out_rel)

    print(f"Generated {len(written)} files into {target}:")
    for f in written:
        print(f"  {f}")
    if make_zip:
        print(f"\nPackage: {write_zip(target)}")
    print()
    print("Next steps:")
    print(f"  cd {target} && ./start.sh")
    if intake is not None:
        print("  Then run `claude` in that folder: CLAUDE.md walks through the first run.")
    elif cfg["has_scout_agent"]:
        print(
            f"  Fill in {target}/{cfg['config_dir_name']}/criteria.md and "
            "search_terms.md before the first scout-agent run."
        )


def port_number(text: str) -> int:
    if not text.isdigit() or not 1024 <= int(text) <= 65535:
        raise argparse.ArgumentTypeError("port must be a number from 1024 to 65535")
    return int(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(usage=__doc__.split("Reads")[0].replace("Usage:", "").strip())
    parser.add_argument("config")
    parser.add_argument("target_dir")
    parser.add_argument("--intake")
    parser.add_argument("--db-name")
    parser.add_argument("--port", type=port_number, metavar="N")
    parser.add_argument("--zip", action="store_true")
    args = parser.parse_args()
    try:
        generate(args.config, args.target_dir, args.intake, args.db_name, args.port, args.zip)
    except FileNotFoundError as e:
        print(f"File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"config.json isn't valid JSON: {e}")
        sys.exit(1)
    except (ConfigError, intake_mod.IntakeError) as e:
        print(str(e))
        sys.exit(1)
