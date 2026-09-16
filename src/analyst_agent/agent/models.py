import sys

from analyst_agent.agent.aws import (
    AwsCredentialsUnavailable,
    list_claude_models,
    list_inference_profiles,
)
from analyst_agent.config import get_settings


def main() -> int:
    settings = get_settings()
    print(f"profile={settings.aws_profile or '<default chain>'}  region={settings.aws_region}\n")

    try:
        models = list_claude_models()
        profiles = list_inference_profiles()
    except AwsCredentialsUnavailable as exc:
        print(exc, file=sys.stderr)
        return 2

    if not models and not profiles:
        print("No Claude models are enabled on this account.")
        print("Enable model access in the Bedrock console, then re-run.")
        return 1

    if profiles:
        print("Inference profiles (use these for cross-region models):")
        for p in profiles:
            print(f"  {p['profile_id']:58} {p['name']}")
        print()

    if models:
        print("Foundation models:")
        for m in models:
            on_demand = "ON_DEMAND" in m["inference_types"]
            note = "" if on_demand else "  (requires an inference profile)"
            print(f"  {m['model_id']:58} {m['name']}{note}")
        print()

    print("Set the chosen identifier as BEDROCK_MODEL_ID in .env.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
