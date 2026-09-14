from __future__ import annotations

import os
from dataclasses import fields

ENV_PREFIX = "MEMENTO_"
LEGACY_ENV_PREFIXES = ("MEMORY_", "SESSION_RAG_")


def env_value(name: str, default: str | None = None) -> str | None:
    """Read canonical MEMENTO_* configuration, falling back through each
    prior name's prefix (MEMORY_*, then SESSION_RAG_*) in order."""

    value = os.getenv(ENV_PREFIX + name)
    if value is not None:
        return value
    for legacy_prefix in LEGACY_ENV_PREFIXES:
        value = os.getenv(legacy_prefix + name)
        if value is not None:
            return value
    return default


def config_from_env(cls):
    """Build a frozen dataclass config from MEMORY_<FIELD_NAME> env
    vars, falling back to each field's own default. Shared by every
    provisional, tunable-constants config (RetrievalConfig, HookConfig, ...)
    so env-parsing semantics live in exactly one place."""

    defaults = cls()
    overrides = {}
    for field in fields(cls):
        raw = env_value(field.name.upper())
        if raw is None:
            continue
        overrides[field.name] = int(raw) if field.type == "int" else float(raw)
    return cls(**{**{f.name: getattr(defaults, f.name) for f in fields(cls)}, **overrides})
