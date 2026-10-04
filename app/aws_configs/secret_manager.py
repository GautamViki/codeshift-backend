import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


def get_aws_secret(secret_name: str, region_name: str = "us-east-1") -> str | None:
    """
    Safely retrieves a parameter from AWS SSM Parameter Store if boto3
    and valid AWS credentials are configured.
    """
    try:
        aws_client = boto3.client("ssm", region_name=region_name)
        response = aws_client.get_parameter(Name=secret_name, WithDecryption=True)
        return response.get("Parameter", {}).get("Value")
    except ImportError:
        logger.debug("boto3 is not installed. Skipping AWS SSM secret retrieval.")
        return None
    except (BotoCoreError, ClientError, Exception) as e:
        logger.warning("Could not fetch secret '%s' from AWS SSM: %s", secret_name, e)
        return None
