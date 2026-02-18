from __future__ import annotations

import os
from typing import Mapping, Optional


_SERVERLESS_ENV_KEYS = (
    "VERCEL",
    "AWS_LAMBDA_FUNCTION_NAME",
    "NOW_REGION",
)


def is_serverless_environment(environ: Optional[Mapping[str, str]] = None) -> bool:
    env = os.environ if environ is None else environ
    for key in _SERVERLESS_ENV_KEYS:
        raw = str(env.get(key, "")).strip()
        if raw:
            return True
    return False


def stateful_run_api_supported(environ: Optional[Mapping[str, str]] = None) -> bool:
    return not is_serverless_environment(environ)


def stateful_run_api_unsupported_detail() -> str:
    return (
        "Stateful /api/run playback endpoints are disabled on serverless deployment "
        "(VERCEL/Lambda) because run state is process-memory only. "
        "Deploy backend as a persistent service (for example Render/Railway/Fly.io)."
    )
