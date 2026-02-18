import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import boto3
import json
import logging
from src.DTO.dto import StoryProcessException
from botocore.config import Config
from src.secret_manager.secret_manager import get_secret_contents

logger = logging.getLogger(__name__)

class AIService:
    # SQ_NO_1.168 - SQ_NO_185: AI Service Integration - handles Bedrock API calls with model selection and token counting
    def llm_call(self, model_name: str, prompt: str):
        logger.info(f"Making LLM call to model: {model_name}")
        try:
            try:
                secrets = get_secret_contents()
            except Exception as e:
                raise StoryProcessException("AIService.py", "llm_call", "Failed to get secrets", str(e))

            region = secrets.get("REGION_NAME", "us-east-1")
            config = Config(    read_timeout=180,  # 3 minutes (in seconds) 
                               connect_timeout=60,  # 1 minute for connection 
                                     retries={'max_attempts': 3})
 
            # Determine model ID based on model name
            model_id = secrets.get(model_name)
            logger.debug(f"Using model_id: {model_id} for model: {model_name}")
            
            bedrock_client = boto3.client("bedrock-runtime", region_name=region,config =config)
            
            messages = [{"role": "user", "content": [{"text": prompt}]}]
            response = bedrock_client.converse(
                modelId=model_id,
                messages=messages,
                inferenceConfig={"maxTokens": 3600, "temperature": 0.7}
            )
            
            # Check response status
            response_metadata = response.get('ResponseMetadata', {})
            status_code = response_metadata.get('HTTPStatusCode')
            logger.debug(f"Bedrock API response status: {status_code}")
            if status_code != 200:
                raise StoryProcessException("AIService.py", "llm_call", f"Bedrock API call failed with status: {status_code}", "API Error")
            
            # Find the text content (skip reasoning content)
            content = response["output"]["message"]["content"]
            response_text = None
            for item in content:
                if "text" in item:
                    response_text = item["text"]
                    break
            
            if response_text is None:
                raise Exception("No text content found in response")
            input_tokens = response["usage"]["inputTokens"]
            output_tokens = response["usage"]["outputTokens"]
            logger.info(f"LLM call completed for {model_name}. Input tokens: {input_tokens}, Output tokens: {output_tokens}")
            
            return {
                "status": 200,
                "response_text": response_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }
        except Exception as e:
            logger.error(f"Error in LLM call for model {model_name}: {str(e)}")
            raise StoryProcessException("AIService.py", "llm_call", "Failed to call LLM", str(e))