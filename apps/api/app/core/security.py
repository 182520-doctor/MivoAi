"""Local browser origin policy for state-changing API requests."""


def is_origin_allowed(origin: str | None, allowed_origins: tuple[str, ...]) -> bool:
    """Allow non-browser clients and only configured origins from browsers."""

    return origin is None or origin in allowed_origins
