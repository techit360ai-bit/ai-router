"""Dedicated AWS credentials for Bedrock, kept apart from the default credential chain.

The default chain (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) belongs to the deploy user that
the S3 storage client uses. Bedrock reads its own pair so neither can break the other.
"""
import os
from typing import Dict


def bedrock_client_kwargs() -> Dict[str, str]:
    key = os.getenv("BEDROCK_AWS_ACCESS_KEY_ID", "").strip()
    secret = os.getenv("BEDROCK_AWS_SECRET_ACCESS_KEY", "").strip()
    if key and secret:
        return {"aws_access_key_id": key, "aws_secret_access_key": secret}
    return {}
