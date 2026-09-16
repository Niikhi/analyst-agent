import sys

from analyst_agent.agent.aws import AwsCredentialsUnavailable, claude_model_ids
from analyst_agent.config import get_settings


def main() -> int:
    settings = get_settings()
    print(f"profile={settings.aws_profile or '<default chain>'}  region={settings.aws_region}\n")

    try:
        ids = claude_model_ids()
    except AwsCredentialsUnavailable as exc:
        print(exc, file=sys.stderr)
        return 2

    if not ids:
        print("No Claude models are enabled. Request access in the Bedrock console.")
        return 1

    for model_id in ids:
        marker = "  <- current" if model_id == settings.bedrock_model_id else ""
        print(f"  {model_id}{marker}")

    if settings.bedrock_model_id not in ids:
        print(f"\nBEDROCK_MODEL_ID is set to {settings.bedrock_model_id!r}, which is not listed.")
        print("Pick one above and set it in .env.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
