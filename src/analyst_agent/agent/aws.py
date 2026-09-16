from functools import lru_cache

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, TokenRetrievalError

from analyst_agent.config import get_settings


class AwsCredentialsUnavailable(RuntimeError):
    pass


SSO_HINT = (
    "AWS credentials for profile {profile!r} are unavailable or expired. "
    "Refresh them with:\n\n    aws sso login --profile {profile}\n"
)


@lru_cache
def session() -> boto3.Session:
    settings = get_settings()
    return boto3.Session(profile_name=settings.aws_profile, region_name=settings.aws_region)


def bedrock_runtime():
    return session().client("bedrock-runtime")


def bedrock_control():
    return session().client("bedrock")


def credentials_hint() -> str:
    return SSO_HINT.format(profile=get_settings().aws_profile or "default")


def wrap_credential_error(exc: Exception) -> Exception:
    if isinstance(exc, (TokenRetrievalError, NoCredentialsError)):
        return AwsCredentialsUnavailable(f"{credentials_hint()}\n({exc})")
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"ExpiredTokenException", "UnrecognizedClientException", "InvalidSignatureException"}:
            return AwsCredentialsUnavailable(f"{credentials_hint()}\n({exc})")
    return exc


def list_claude_models() -> list[dict[str, str]]:
    try:
        summaries = bedrock_control().list_foundation_models()["modelSummaries"]
    except Exception as exc:
        raise wrap_credential_error(exc) from exc

    models = []
    for m in summaries:
        model_id = m.get("modelId", "")
        if "claude" not in model_id.lower():
            continue
        if "TEXT" not in m.get("outputModalities", ["TEXT"]):
            continue
        models.append(
            {
                "model_id": model_id,
                "name": m.get("modelName", ""),
                "streaming": str(m.get("responseStreamingSupported", False)),
                "inference_types": ",".join(m.get("inferenceTypesSupported", [])),
            }
        )
    return sorted(models, key=lambda m: m["model_id"])


def list_inference_profiles() -> list[dict[str, str]]:
    try:
        profiles = bedrock_control().list_inference_profiles()["inferenceProfileSummaries"]
    except Exception as exc:
        raise wrap_credential_error(exc) from exc

    return sorted(
        (
            {"profile_id": p.get("inferenceProfileId", ""), "name": p.get("inferenceProfileName", "")}
            for p in profiles
            if "claude" in p.get("inferenceProfileId", "").lower()
        ),
        key=lambda p: p["profile_id"],
    )
