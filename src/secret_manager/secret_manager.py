import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import boto3
import json
from src.DTO.dto import StoryProcessException


def get_secret_contents():
    try:        
        client = boto3.client(service_name='secretsmanager', region_name='us-east-1')
        secret_id = "arn:aws:secretsmanager:us-east-1:242201302730:secret:zebnewsgenie-eus1-story-generation-poc-secrets-A8cgLB"
        get_secret_value_response = client.get_secret_value(SecretId=secret_id)
        if 'SecretString' in get_secret_value_response:
            secrets = json.loads(get_secret_value_response['SecretString'])
            return secrets
        else:
            return ("No secret data found in response")
    except Exception as e:
        raise StoryProcessException("Secret_manager","get_secret_contents()", "Failed to process to secret", str(e))
       