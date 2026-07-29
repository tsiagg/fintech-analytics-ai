"""Semantic-layer catalog for the BI Assistant.

Builds the **allowlist** of metrics and dimensions the assistant is permitted to
query, parsed directly from the dbt MetricFlow YAML so it always matches the
warehouse. The assistant never writes SQL — it may only request a metric +
dimensions from this catalog, which MetricFlow then compiles and runs.

Source of truth:
  dbt/models/semantic_models/metrics.yml          (metric definitions)
  dbt/models/semantic_models/semantic_*.yml       (measures + dimensions)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEMANTIC_DIR = _REPO_ROOT / "dbt" / "models" / "semantic_models"

# Time grains available downstream of a base aggregation grain.
_GRAIN_LADDER = ["day", "week", "month", "quarter", "year"]


@dataclass(frozen=True)
class SemanticModel:
    name: str
    primary_entity: str
    base_time_grain: str
    categorical_dimensions: list[str]  # group-by names, e.g. "user_day__reporting_region"
    measures: set[str]


@dataclass(frozen=True)
class MetricInfo:
    name: str
    label: str
    description: str
    metric_type: str
    semantic_model: str | None
    dimensions: list[str] = field(default_factory=list)  # categorical group-by names
    time_grains: list[str] = field(default_factory=list)  # e.g. ["day", "week", ...]

    @property
    def time_group_bys(self) -> list[str]:
        return [f"metric_time__{g}" for g in self.time_grains]

    @property
    def all_group_bys(self) -> list[str]:
        return self.dimensions + self.time_group_bys


@dataclass(frozen=True)
class Catalog:
    metrics: dict[str, MetricInfo]
    models: dict[str, SemanticModel]

    @property
    def metric_names(self) -> set[str]:
        return set(self.metrics)

    def group_bys_for(self, metric_names: list[str]) -> set[str]:
        """Group-bys allowed for ALL of the requested metrics (intersection)."""
        allowed: set[str] | None = None
        for name in metric_names:
            info = self.metrics.get(name)
            if info is None:
                return set()
            this = set(info.all_group_bys)
            allowed = this if allowed is None else (allowed & this)
        return allowed or set()


def _grains_from_base(base: str) -> list[str]:
    if base not in _GRAIN_LADDER:
        return [base]
    return _GRAIN_LADDER[_GRAIN_LADDER.index(base):]


def _load_semantic_models() -> dict[str, SemanticModel]:
    models: dict[str, SemanticModel] = {}
    for path in sorted(_SEMANTIC_DIR.glob("semantic_*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for sm in doc.get("semantic_models", []):
            name = sm["name"]
            primary = next(
                (e["name"] for e in sm.get("entities", []) if e.get("type") == "primary"),
                name,
            )
            base_grain = (sm.get("defaults") or {}).get("agg_time_dimension", "")
            cat_dims: list[str] = []
            base_time_grain = "day"
            for dim in sm.get("dimensions", []):
                if dim.get("type") == "categorical":
                    cat_dims.append(f"{primary}__{dim['name']}")
                elif dim.get("type") == "time":
                    grain = (dim.get("type_params") or {}).get("time_granularity", "day")
                    if dim["name"] == base_grain or not base_time_grain:
                        base_time_grain = grain
            measures = {m["name"] for m in sm.get("measures", [])}
            models[name] = SemanticModel(
                name=name,
                primary_entity=primary,
                base_time_grain=base_time_grain,
                categorical_dimensions=cat_dims,
                measures=measures,
            )
    return models


def _measure_to_model(models: dict[str, SemanticModel]) -> dict[str, SemanticModel]:
    out: dict[str, SemanticModel] = {}
    for model in models.values():
        for measure in model.measures:
            out[measure] = model
    return out


def _resolve_measures(metric_name: str, defs: dict[str, dict], seen: set[str]) -> list[str]:
    """Walk a metric to its underlying measure name(s)."""
    if metric_name in seen:
        return []
    seen.add(metric_name)
    spec = defs.get(metric_name)
    if not spec:
        return []
    mtype = spec.get("type")
    params = spec.get("type_params") or {}
    if mtype in ("simple", "cumulative"):
        measure = params.get("measure")
        return [measure] if measure else []
    if mtype == "ratio":
        num = (params.get("numerator") or {})
        num_name = num.get("name") if isinstance(num, dict) else num
        return _resolve_measures(num_name, defs, seen) if num_name else []
    if mtype == "derived":
        measures: list[str] = []
        for ref in params.get("metrics", []):
            ref_name = ref.get("name") if isinstance(ref, dict) else ref
            if ref_name:
                measures.extend(_resolve_measures(ref_name, defs, seen))
        return measures
    return []


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    models = _load_semantic_models()
    measure_model = _measure_to_model(models)

    metrics_doc = yaml.safe_load(
        (_SEMANTIC_DIR / "metrics.yml").read_text(encoding="utf-8")
    ) or {}
    raw_metrics = metrics_doc.get("metrics", [])
    defs = {m["name"]: m for m in raw_metrics}

    metrics: dict[str, MetricInfo] = {}
    for spec in raw_metrics:
        name = spec["name"]
        measures = _resolve_measures(name, defs, set())
        model = next((measure_model[m] for m in measures if m in measure_model), None)
        if model is not None:
            dims = list(model.categorical_dimensions)
            grains = _grains_from_base(model.base_time_grain)
        else:
            dims, grains = [], ["day", "week", "month", "quarter", "year"]
        metrics[name] = MetricInfo(
            name=name,
            label=spec.get("label", name),
            description=spec.get("description", "").strip(),
            metric_type=spec.get("type", "simple"),
            semantic_model=model.name if model else None,
            dimensions=dims,
            time_grains=grains,
        )
    return Catalog(metrics=metrics, models=models)


def format_catalog_for_prompt() -> str:
    """Compact metric+dimension listing for the LLM planner system prompt."""
    catalog = get_catalog()
    lines: list[str] = []
    for info in catalog.metrics.values():
        dims = ", ".join(info.dimensions) if info.dimensions else "(none)"
        grains = ", ".join(info.time_group_bys)
        lines.append(
            f"- {info.name} [{info.metric_type}] — {info.label}. "
            f"dimensions: {dims}. time: {grains}"
        )
    return "\n".join(lines)


def render_catalog_markdown() -> str:
    """Human-readable catalog for the 'what can you report on?' answer."""
    catalog = get_catalog()
    by_model: dict[str, list[MetricInfo]] = {}
    for info in catalog.metrics.values():
        by_model.setdefault(info.semantic_model or "other", []).append(info)

    titles = {
        "daily_user_activity": "Daily user activity (company-wide, by day)",
        "company_performance": "Company performance vs targets (by month)",
        "daily_symbol_activity": "Instrument / symbol activity (by day)",
        "other": "Other metrics",
    }

    parts: list[str] = ["Here is what I can report on. I use only these governed "
                        "metrics and dimensions from the semantic layer — I never write ad-hoc SQL.\n"]
    for model_name, infos in by_model.items():
        parts.append(f"\n**{titles.get(model_name, model_name)}**")
        dims = sorted({d for i in infos for d in i.dimensions})
        if dims:
            parts.append(f"\n_Dimensions:_ {', '.join(dims)}")
        grains = sorted({g for i in infos for g in i.time_grains})
        if grains:
            parts.append(f"\n_Time grains:_ {', '.join(grains)}")
        parts.append("\n\n_Metrics:_")
        for info in infos:
            parts.append(f"\n- **{info.name}** — {info.label}")
    return "".join(parts)
