#!/usr/bin/env python3
"""Configure non-secret Bedrock settings from a shared AWS profile.

Docker Compose does not automatically mount ``~/.aws``. This helper copies only
the profile's region and Bedrock feature flags into an env file. Credentials
stay in the runtime environment, deployment secret store, or IAM role and are
never written to the repository working tree by this script.
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

    if not credentials.has_option(args.profile, "aws_access_key_id") or not credentials.has_option(
        args.profile, "aws_secret_access_key"
    ):
        parser.error(f"profile '{args.profile}' is missing AWS access or secret key")

    config_section = _section_for_profile(args.profile)
    region = config.get(config_section, "region", fallback="").strip() or "us-east-1"

    env_path = Path(args.env_file)
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    updates: dict[str, str | None] = {"AWS_REGION": region}
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

    print(
        f"updated non-secret settings in {env_path} from AWS profile "
        f"'{args.profile}' in {region}"
    )
    print("keys: " + ", ".join(updates))
    print("AWS credentials were not copied; keep them in the runtime secret store or IAM role")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
