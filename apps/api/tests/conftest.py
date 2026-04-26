from __future__ import annotations

import weakref
from typing import Any

import sqlalchemy


_ORIGINAL_CREATE_ENGINE = sqlalchemy.create_engine


def _create_engine_with_dispose_finalizer(*args: Any, **kwargs: Any):
    engine = _ORIGINAL_CREATE_ENGINE(*args, **kwargs)
    weakref.finalize(engine, engine.dispose)
    return engine


sqlalchemy.create_engine = _create_engine_with_dispose_finalizer
