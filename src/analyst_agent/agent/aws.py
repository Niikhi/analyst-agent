from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

from analyst_agent.config import get_settings

CREDENTIAL_CODES = {
    "ExpiredToken", "ExpiredTokenException", "InvalidSignatureException",
    "UnrecognizedClientException", "AccessDenied", "AccessDeniedException",
}


class AwsCredentialsUnavailable(RuntimeError):
    pass


@lru_cache
def session() -> boto3.Session:
    settings = get_settings()
    return boto3.Session(profile_name=settings.aws_profile, region_name=settings.aws_region)


def client(service: str):
    return session().client(service)


def as_credential_error(exc: Exception) -> Exception:
    code = type(exc).__name__
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", code)
    if code in CREDENTIAL_CODES or "Token" in code or "Credential" in code:
        profile = get_settings().aws_profile or "default"
        return AwsCredentialsUnavailable(
            f"AWS credentials for profile '{profile}' are missing or expired.\n"
            f"Refresh them with:  aws sso login --profile {profile}"
        )
    return exc


def claude_model_ids() -> list[str]:
    bedrock = client("bedrock")
    try:
        profiles = bedrock.list_inference_profiles()["inferenceProfileSummaries"]
        models = bedrock.list_foundation_models()["modelSummaries"]
    except Exception as exc:
        raise as_credential_error(exc) from exc

    ids = [p["inferenceProfileId"] for p in profiles]
    ids += [m["modelId"] for m in models if "ON_DEMAND" in m.get("inferenceTypesSupported", [])]
    return sorted({i for i in ids if "claude" in i.lower()})
