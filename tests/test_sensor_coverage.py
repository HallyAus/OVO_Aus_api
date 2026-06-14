"""Namespace-coverage contract — the regression guard for the issue #74 bug class.

#74 was: analytics *computed* `hourly.time_of_use` every refresh but no sensor
ever read it, so the values never reached Home Assistant ("orphaned namespace").
A one-off test for the TOU sensors only covers that one instance. This test
covers the whole class:

Every analytics namespace the pipeline produces must be one of:
  1. consumed  — referenced somewhere in the sensor layer, or
  2. internal  — listed in INTERNAL_NAMESPACES (raw scratch / feeds / redundant), or
  3. known gap — listed in KNOWN_UNEXPOSED_GAPS (computed user-facing data not yet
                 surfaced; documented tech debt found by the orphan audit).

If a NEW computed namespace appears that is none of these, `test_no_orphaned_namespaces`
FAILS, forcing a deliberate choice: expose it, mark it internal, or record it as a
known gap. Conversely, once a known gap is exposed, `test_classified_namespaces_stay_unexposed`
fails until it is removed from the list — so the gap list cannot silently rot.

Granularity is top-level `coordinator.data` keys plus first-level `hourly.*` keys
(the level at which #74 occurred). Finer partial-exposure gaps inside `time_of_use`
(shoulder / ev_offpeak / free / other) and `peak_4hour_window` timing keys are
tracked in the orphan-audit report, not enforced here (their leaf tokens collide
with unrelated rate strings, making a source scan unreliable).
"""

from pathlib import Path

from custom_components.ovo_energy_au.analytics import (
    compute_insights,
    process_hourly_data,
    process_interval_data,
)

# The entire sensor layer. Anything a sensor (value_fn lambda or specialized
# class) reads out of coordinator.data appears as a quoted key string here.
_PKG = Path(__file__).resolve().parents[1] / "custom_components" / "ovo_energy_au"
_SENSOR_SOURCE = "\n".join(
    (_PKG / rel).read_text(encoding="utf-8")
    for rel in ("sensor.py", "sensors/definitions.py", "sensors/base.py")
)

# Produced but legitimately NOT exposed as sensors: raw API scratch, internal
# feeds for other analytics, or redundant variants of already-surfaced data.
INTERNAL_NAMESPACES = {
    "hourly.hourly_rates_breakdown",  # redundant: per-rate split already surfaced via {period}.rate_breakdown
    "hourly.ev_usage_monthly",        # redundant copy of monthly EV (monthly_ev_charging_* sensors exist)
    "hourly.ev_usage_yearly",         # bounded by the ~7-day hourly window; a "yearly" sensor would mislead
}

# Produced user-facing data NOT yet surfaced — documented tech debt, same bug
# class as #74. Listed so this contract passes today while keeping the gaps
# visible. When one is exposed as a sensor, REMOVE it here (the second test
# enforces that). See the orphan-namespace audit for rationale.
KNOWN_UNEXPOSED_GAPS = {
    "last_3_days",          # full daily-entry list; direct twin of the exposed last_7_days
    "hourly.free_usage",    # MTD FREE_3 {consumption, cost_saved, hours}; cost_saved exposed nowhere
    "hourly.ev_usage",      # MTD EV {consumption, cost, cost_saved, hours}; cost_saved unique
    "hourly.ev_usage_weekly",  # last-7-days EV; there is no weekly EV sensor at all
}


def _produced_namespaces(interval_data, hourly_data, plan_config) -> set[str]:
    """Run the real analytics pipeline and return the namespaces it produces
    (top-level coordinator.data keys + first-level hourly.* keys)."""
    processed = process_interval_data(interval_data)
    processed["hourly"] = process_hourly_data(hourly_data, plan_config)
    compute_insights(processed)
    namespaces = set(processed.keys())
    namespaces |= {f"hourly.{key}" for key in processed["hourly"]}
    return namespaces


def _is_referenced(namespace: str) -> bool:
    """True if the namespace's leaf key is read anywhere in the sensor layer.
    Matches the quoted key (e.g. `"ev_usage"`) so it does not falsely match a
    longer key (`"ev_usage_weekly"`) that merely shares a prefix."""
    leaf = namespace.split(".")[-1]
    return f'"{leaf}"' in _SENSOR_SOURCE or f"'{leaf}'" in _SENSOR_SOURCE


def test_no_orphaned_namespaces(sample_interval_data, sample_hourly_data, plan_config):
    """Every produced namespace must be consumed, internal, or a known gap.

    A failure here means new analytics output is computed but reaches no sensor
    (the #74 bug). Fix by exposing it, adding it to INTERNAL_NAMESPACES, or — if
    it is a deferred user-facing metric — to KNOWN_UNEXPOSED_GAPS."""
    produced = _produced_namespaces(sample_interval_data, sample_hourly_data, plan_config)
    classified = INTERNAL_NAMESPACES | KNOWN_UNEXPOSED_GAPS
    orphans = {ns for ns in produced if not _is_referenced(ns) and ns not in classified}
    assert not orphans, (
        "Orphaned analytics namespace(s) — computed but no sensor reads them "
        "(issue #74 bug class):\n  "
        + "\n  ".join(sorted(orphans))
        + "\n\nResolve each by either: (a) adding a sensor that reads it, "
        "(b) listing it in INTERNAL_NAMESPACES if it is internal scratch, or "
        "(c) listing it in KNOWN_UNEXPOSED_GAPS if it is a deferred user-facing metric."
    )


def test_classified_namespaces_stay_unexposed(
    sample_interval_data, sample_hourly_data, plan_config
):
    """Keep the INTERNAL/KNOWN-GAP lists honest: each entry must still be produced
    (not a stale name) and still unexposed. If a known gap gets a sensor, this
    fails — remove it from the list."""
    produced = _produced_namespaces(sample_interval_data, sample_hourly_data, plan_config)
    for namespace in sorted(INTERNAL_NAMESPACES | KNOWN_UNEXPOSED_GAPS):
        assert namespace in produced, (
            f"{namespace!r} is listed in the coverage contract but the pipeline no "
            f"longer produces it — remove the stale entry."
        )
        assert not _is_referenced(namespace), (
            f"{namespace!r} is now read by a sensor — remove it from "
            f"INTERNAL_NAMESPACES / KNOWN_UNEXPOSED_GAPS so it counts as exposed."
        )


def test_time_of_use_split_is_exposed(sample_interval_data, sample_hourly_data, plan_config):
    """The specific #74 namespace must stay consumed (peak/off_peak split)."""
    produced = _produced_namespaces(sample_interval_data, sample_hourly_data, plan_config)
    assert "hourly.time_of_use" in produced
    assert _is_referenced("hourly.time_of_use"), (
        "hourly.time_of_use is computed but no sensor reads it — this is the exact "
        "regression issue #74 reported."
    )
