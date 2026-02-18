import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.Service.llm.AIService import AIService
from concurrent.futures import ThreadPoolExecutor
import time
import boto3
import logging
from src.DTO.dto import StoryProcessException
from src.DTO.constants import GENERATIVE_PROMPT_VERSIONS
from src.secret_manager.secret_manager import get_secret_contents

logger = logging.getLogger(__name__)

class GenerationService:
    # SQ_NO_1.263 - SQ_NO_1.115: Content Generation - generates improved content using ThreadPoolExecutor for parallel AI model execution
    def multi_generate(self, generator_models: list, content: str, issue_categories: list, preserved_categories: list, current_scores: dict, threshold_score: float):
        logger.info(f"Starting content generation with {len(generator_models)} models for {len(issue_categories)} issue categories")
        try:            
            # Get generation prompt with both issue and preserved categories
            generation_prompt = self.get_generation_prompt(content, issue_categories, preserved_categories, current_scores, threshold_score)
            
            # Multi-threaded processing with max_workers
            max_workers = 2
            
            # Use ThreadPoolExecutor with max_workers
            logger.info(f"Processing {len(generator_models)} generator models with {max_workers} workers")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(self.process_generator_thread, model["model_name"], model["model_id"], generation_prompt) for model in generator_models]
                
                # Collect results
                models_data = [future.result() for future in futures]
            
            return {"models_data": models_data}
            
        except Exception as e:
            raise StoryProcessException("GenerationService.py", "multi_generate", "Failed to generate content", str(e))
    
    # SQ_NO_1.281 - SQ_NO_1.305: Process individual generator model in thread
    def process_generator_thread(self, model_name, model_id, prompt):
        logger.debug(f"Processing generator thread for model: {model_name}")
        try:
            ai_service = AIService()
            model_start_time = time.time()
            response = ai_service.llm_call(model_name, prompt)
            model_end_time = time.time()
            model_execution_time = round(model_end_time - model_start_time,2)
            
            if response.get("status") == 200:
                response_text = response.get("response_text")
                input_tokens = response.get("input_tokens")
                output_tokens = response.get("output_tokens")
                
                story = self.extract_story(response_text)
                
                return {
                    "model_name": model_name,
                    "model_id": model_id,
                    "story": story,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "execution_time": model_execution_time
                }
            else:
                error_message = f"Failed to get response from {model_name}: {response.get('message')}"
                return {
                    "model_name": model_name,
                    "model_id": model_id,
                    "story": "",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "error": error_message,
                    "execution_time": model_execution_time
                }
        except Exception as e:
            return {
                "model_name": model_name,
                "model_id": model_id,
                "story": "",
                "input_tokens": 0,
                "output_tokens": 0,
                "error": str(e),
                "execution_time": 0
            }
    
    # SQ_NO_1.264 - SQ_NO_1.279: Content Generation - creates generation prompt with issue and preserved categories
    def get_generation_prompt(self, content: str, issue_categories: list, preserved_categories: list, current_scores: dict, threshold_score: float):
        try:
            try:
                secrets = get_secret_contents()
            except Exception as e:
                raise StoryProcessException("GenerationService.py", "get_generation_prompt", "Failed to get secrets", str(e))
            
            # AWS Prompt Manager
            region = secrets.get("REGION_NAME", "us-east-1")
            
            bedrock_prompt_client = boto3.client("bedrock-agent", region_name=region)
            
            prompt_id = secrets.get("GENERATION_PROMPT_ID")
            params = {"promptIdentifier": prompt_id}
            prompt_version = GENERATIVE_PROMPT_VERSIONS["GENERATION_PROMPT_VERSION"]
            if prompt_version:
                params["promptVersion"] = prompt_version
            
            prompt_response = bedrock_prompt_client.get_prompt(**params)
            prompt_template = prompt_response["variants"][0]["templateConfiguration"]["text"]["text"]
            
            # Format categories properly as readable lists with scores
            issues_text = "\n".join([f"- {issue}: Score {current_scores.get(issue, 0)} (needs improvement)" for issue in issue_categories]) if issue_categories else "None"
            preserved_text = "\n".join([f"- {cat}: Score {current_scores.get(cat, 0)} (preserve this quality)" for cat in preserved_categories]) if preserved_categories else "None"
            # Replace placeholders in prompt template
            formatted_prompt = prompt_template.replace("{issue_categories}", issues_text)
            formatted_prompt = formatted_prompt.replace("{preserved_categories}", preserved_text)
            formatted_prompt = formatted_prompt.replace("{current_scores}", str(current_scores))
            formatted_prompt = formatted_prompt.replace("{threshold_score}", str(threshold_score))
            formatted_prompt = formatted_prompt.replace("{original_content}", content)
            
            return formatted_prompt
        except Exception as e:
            
            raise StoryProcessException("GenerationService.py", "get_generation_prompt", "Failed to create generation prompt", str(e))
    
    # SQ_NO_1.309 - SQ_NO_1.312: Content Generation - extracts generated story from AI response
    def extract_story(self, response_text: str):
        # Simple extraction - should be enhanced based on actual response format
        return response_text.strip()