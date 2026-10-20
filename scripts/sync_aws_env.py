#!/usr/bin/env python3
"""Copy a shared AWS profile into an env file without printing secrets.

Docker Compose does not automatically mount ``~/.aws``. This keeps the router
on the standard AWS credential chain while making the profile available to the
container through environment variables. Prefer a dedicated IAM principal.
"""

from __future__ import annotations

import argparse
import configparser
import os
import re
from pathlib import Path


def _read_ini(path: Path) -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser()
    parser.read(path)
    return parser


def _section_for_profile(profile: str) -> str:
    return profile if profile == "default" else f"profile {profile}"


def _upsert(text: str, key: str, value: str | None) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if value is None:
        return pattern.sub("", text)
    line = f"{key}={value}"
    return pattern.sub(line, text) if pattern.search(text) else f"{text.rstrip()}\n{line}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE", "default"))
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--enable-bedrock", action="store_true")
    args = parser.parse_args()

    credentials_path = Path(
        os.getenv("AWS_SHARED_CREDENTIALS_FILE", Path.home() / ".aws" / "credentials")
    )
    config_path = Path(os.getenv("AWS_CONFIG_FILE", Path.home() / ".aws" / "config"))
    credentials = _read_ini(credentials_path)
    config = _read_ini(config_path)
    if not credentials.has_section(args.profile):
        parser.error(f"profile '{args.profile}' is missing from {credentials_path}")

    access_key = credentials.get(args.profile, "aws_access_key_id", fallback="").strip()
    secret_key = credentials.get(args.profile, "aws_secret_access_key", fallback="").strip()
    session_token = credentials.get(args.profile, "aws_session_token", fallback="").strip()
    if not access_key or not secret_key:
        parser.error(f"profile '{args.profile}' is missing AWS access or secret key")

    config_section = _section_for_profile(args.profile)
    region = config.get(config_section, "region", fallback="").strip() or "us-east-1"

    env_path = Path(args.env_file)
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    updates: dict[str, str | None] = {
        "AWS_ACCESS_KEY_ID": access_key,
        "AWS_SECRET_ACCESS_KEY": secret_key,
        "AWS_SESSION_TOKEN": session_token or None,
        "AWS_REGION": region,
    }
    if args.enable_bedrock:
        updates.update({
            "BEDROCK_ENABLED": "true",
            "BEDROCK_REGION": region,
            "AI_BEDROCK_LIVE_PROBE": "true",
        })
    for key, value in updates.items():
        text = _upsert(text, key, value)
    env_path.write_text(text, encoding="utf-8")
    env_path.chmod(0o600)

    print(f"updated {env_path} from AWS profile '{args.profile}' in {region}")
    print("keys: " + ", ".join(updates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
