# SQ_NO_1.16 - SQ_NO_1.21: import required packages 
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.Service.llm.AIService import AIService
from src.Service.evaluation.MetricsService import MetricsService
import time
import boto3
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from src.DTO.dto import StoryProcessException
from src.DTO.constants import JUDGING_PROMPT_VERSIONS
from src.secret_manager.secret_manager import get_secret_contents

logger = logging.getLogger(__name__)

class JudgingService:
    # SQ_NO_1.137 - SQ_NO_1.75: Content Evaluation - evaluates content using AI models with ThreadPoolExecutor
    def identify_issue_categories(self, text: str, categories: list, judging_models: list, threshold_score: float):
        logger.info(f"Starting content evaluation with {len(judging_models)} models and threshold: {threshold_score}")
        try:
            metrics_service = MetricsService()
            
            # Get judging prompt
            judging_prompt = self.get_judging_prompt(text, categories, threshold_score)
            
            # Multi-threaded processing with max_workers
            max_workers = 2  
            results = {}
            
            # Use ThreadPoolExecutor with max_workers
            logger.info(f"Processing {len(judging_models)} judging models with {max_workers} workers")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(self.process_judge_thread, model["model_name"], model["model_id"], judging_prompt) for model in judging_models]
                
                # Collect results
                for future in futures:
                    result = future.result()
                    results[result["model_name"]] = result
            
            # Process results dynamically based on available models
            model_results = list(results.values())
            scores_list = [result.get("scores", {}) for result in model_results]
            comments_list = [result.get("comments", {}) for result in model_results]
            
            # Average scores and comments dynamically
            if len(scores_list) > 0:
                averaged_result = metrics_service.average_scores_and_comments(scores_list, comments_list)
            else:
                # No valid results
                averaged_result = {"status": 200, "data": {"scores": {}, "comments": {}}}
  
            averaged_scores = averaged_result["data"]["scores"]
            merged_comments = averaged_result["data"]["comments"]
            
            # Identify issue categories
            issue_categories = [category for category, score in averaged_scores.items() if score > threshold_score]
            logger.info(f"Identified {len(issue_categories)} issue categories above threshold: {issue_categories}")
            
            # Prepare models_data for database storage
            models_data = []
            for _, model_result in results.items():
                models_data.append({
                    "model_id": model_result.get("model_id"),
                    "scores": model_result.get("scores", {}),
                    "comments": model_result.get("comments", {}),
                    "input_tokens": model_result.get("input_tokens", 0),
                    "output_tokens": model_result.get("output_tokens", 0),
                    "execution_time": model_result.get("execution_time", 0.0)
                })
            
            return {
                "issue_categories": issue_categories,
                "scores": averaged_scores,
                "comments": merged_comments,
                "models_data": models_data
            }
            
        except Exception as e:
            raise StoryProcessException("JudgingService.py", "identify_issue_categories", "Failed to evaluate content", str(e))
    
    # SQ_NO_1.163 - SQ_NO_1.206: Process individual judge model in thread
    def process_judge_thread(self, model_name, model_id, prompt):
        logger.debug(f"Processing judge thread for model: {model_name}")
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
                
                parsed_result = self.extract_scores_and_comments(response_text)
                
                return {
                    "model_name": model_name,
                    "model_id": model_id,
                    "scores": parsed_result["scores"],
                    "comments": parsed_result["comments"],
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "execution_time": model_execution_time
                }
            else:
                error_message = f"Failed to get response from {model_name}: {response.get('message')}"
                return {
                    "model_name": model_name,
                    "model_id": model_id,
                    "scores": {},
                    "comments": {},
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "error": error_message,
                    "execution_time": model_execution_time
                }
        except Exception as e:
            return {
                "model_name": model_name,
                "model_id": model_id,
                "scores": {},
                "comments": {},
                "error": str(e),
                "execution_time": 0
            }
    
    # SQ_NO_1.144 - SQ_NO_1.157: Content Evaluation - creates judging prompt with categories and content
    def get_judging_prompt(self, text, categories, threshold_score: float):
        try:
            try:
                secrets = get_secret_contents()
            except Exception as e:
                raise StoryProcessException("JudgingService.py", "get_judging_prompt", "Failed to get secrets", str(e))
            
            # AWS Prompt Manager
            region = secrets.get("REGION_NAME", "us-east-1")
            
            bedrock_prompt_client = boto3.client("bedrock-agent", region_name=region)
            
            prompt_id = secrets.get("JUDGING_PROMPT_ID")
            params = {"promptIdentifier": prompt_id}
            prompt_version = JUDGING_PROMPT_VERSIONS["JUDGING_PROMPT_VERSION"]
            if prompt_version:
                params["promptVersion"] = prompt_version
            
            prompt_response = bedrock_prompt_client.get_prompt(**params)
            prompt_template = prompt_response["variants"][0]["templateConfiguration"]["text"]["text"]
            
            categories_text = "\n".join([
                f"- {cat['category_name']}: {cat['description']}\n  Evaluation Criteria: {cat['evaluation_criteria']}"
                for cat in categories
            ])
            formatted_prompt = prompt_template.replace("{{CATEGORIES}}", categories_text)
            formatted_prompt = formatted_prompt.replace("{{CONTENT}}", text)
            formatted_prompt = formatted_prompt.replace("{{threshold_score}}", str(threshold_score))
            
            return formatted_prompt
        except Exception as e:
            raise StoryProcessException("JudgingService.py", "get_judging_prompt", "Failed to create judging prompt", str(e))
    
    # SQ_NO_1.189 - SQ_NO_1.195: Score Processing - parses AI responses to extract scores and comments
    def extract_scores_and_comments(self, response_text):
        try:
            # Clean response text - remove markdown code blocks and HTML entities
            clean_text = response_text.strip()
            if clean_text.startswith('```json'):
                clean_text = clean_text[7:]  # Remove ```json
            if clean_text.startswith('```'):
                clean_text = clean_text[3:]   # Remove ```
            if clean_text.endswith('```'):
                clean_text = clean_text[:-3]  # Remove trailing ```
            
            # Replace HTML entities
            clean_text = clean_text.replace('&quot;', '"').replace('&#39;', "'")
            clean_text = clean_text.strip()
            
            # Try to parse as JSON, handle truncated responses
            try:
                parsed_json = json.loads(clean_text)
            except json.JSONDecodeError as e:
                # If JSON is truncated, try to extract what we can
                if "Unterminated string" in str(e):
                    # Find the last complete category entry
                    lines = clean_text.split('\n')
                    valid_json = []
                    brace_count = 0
                    in_string = False
                    escape_next = False
                    
                    for char in clean_text:
                        if escape_next:
                            escape_next = False
                            continue
                        if char == '\\' and in_string:
                            escape_next = True
                            continue
                        if char == '"' and not escape_next:
                            in_string = not in_string
                        if not in_string:
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                        valid_json.append(char)
                        
                        # If we have balanced braces and we're not in a string, try to parse
                        if brace_count == 0 and not in_string and len(valid_json) > 10:
                            test_json = ''.join(valid_json)
                            try:
                                parsed_json = json.loads(test_json)
                                break
                            except:
                                continue
                    else:
                        # If we couldn't fix it, return empty results
                        return {"scores": {}, "comments": {}}
                else:
                    raise
            scores = {}
            comments = {}
            
            # Handle the actual AI response format: {"categories": {"CategoryName": {"score": 0.6, "comments": "..."}}}
            if "categories" in parsed_json:
                categories_data = parsed_json["categories"]
                for category_name, category_data in categories_data.items():
                    if isinstance(category_data, dict):
                        scores[category_name] = category_data.get("score", 0.0)
                        comments[category_name] = category_data.get("comments", "")
            
            # Fallback: check for direct scores/comments structure
            elif "scores" in parsed_json:
                scores = parsed_json.get("scores", {})
                comments = parsed_json.get("comments", {})
            
            return {"scores": scores, "comments": comments}
            
        except json.JSONDecodeError as e:
            raise StoryProcessException("JudgingService.py", "extract_scores_and_comments", "Failed to parse JSON response", str(e))