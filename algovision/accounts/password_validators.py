from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class _HIBPConfig:
    enabled: bool = True
    timeout_seconds: int = 3
    hibp_api_base_url: str = "https://api.pwnedpasswords.com"


class HaveIBeenPwnedPasswordValidator:
    """
    Checks passwords against HIBP Pwned Passwords using the k-anonymity API.
    No password is sent to the service; only a SHA-1 prefix is used.
    """

    def __init__(
        self,
        enabled: bool = True,
        timeout_seconds: int = 3,
        hibp_api_base_url: str = "https://api.pwnedpasswords.com",
    ):
        self._cfg = _HIBPConfig(
            enabled=bool(enabled),
            timeout_seconds=int(timeout_seconds),
            hibp_api_base_url=str(hibp_api_base_url).rstrip("/"),
        )

    def validate(self, password: str, user=None) -> None:  # noqa: ANN001
        if not self._cfg.enabled:
            return

        if not password:
            return

        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()  # noqa: S324
        prefix, suffix = sha1[:5], sha1[5:]

        count = self._hibp_suffix_count(prefix=prefix, suffix=suffix)
        if count is None:
            # If the service is unavailable, do not block user signups/changes.
            # Local validators still apply.
            return

        if count > 0:
            raise ValidationError(
                _(
                    "This password has appeared in a public data breach and cannot be used."
                ),
                code="password_pwned",
            )

    def get_help_text(self) -> str:
        return _(
            "Your password can't be a commonly used password or one found in public data breaches."
        )

    def _hibp_suffix_count(self, *, prefix: str, suffix: str) -> Optional[int]:
        url = f"{self._cfg.hibp_api_base_url}/range/{prefix}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "algovision-django/hibp-validator",
                "Add-Padding": "true",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._cfg.timeout_seconds) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
            return None

        # Response lines: "<HASH_SUFFIX>:<COUNT>"
        # Example: "0031B...:2"
        for line in body.splitlines():
            if ":" not in line:
                continue
            sfx, cnt = line.split(":", 1)
            if sfx.strip().upper() == suffix:
                try:
                    return int(cnt.strip())
                except ValueError:
                    return None
        return 0

