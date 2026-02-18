# SQ_NO_1.7 - SQ_NO_1.12:  import required packages 
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from src.Service.evaluation.JudgingService import JudgingService
from src.Service.generation.GenerationService import GenerationService
from src.Service.analysis.AnalysisService import AnalysisService
from src.Repository.repositoryExecute import RepositoryExecute
from src.DTO.dto import StoryProcessException
from concurrent.futures import ThreadPoolExecutor

import time
import json
import logging

logger = logging.getLogger(__name__)

class StoryProcessingService:
    # SQ_NO_1.48 - SQ_NO_1.109: Content Processing Initialization - validates payload, extracts source_content and threshold_score, initializes timing
    def process_content(self, payload: dict):
        logger.info("Starting content processing")
        try:
            if "source_content" not in payload or not payload["source_content"]:
                return {"status_code": 400, "message": "Missing required source_content"}
            if "threshold_score" not in payload:
                return {"status_code": 400, "message": "Missing required threshold_score"}
            source_content = payload.get("source_content")
            threshold_score = payload.get("threshold_score")
            start_time = time.time()
            repo = RepositoryExecute()
            
            # Get models
            logger.info("Retrieving models from database")
            models_response = repo.get_models()
            if models_response["data"] :
                models = models_response.get("data")
                judging_models = [m for m in models if m["model_type"] == "JUDGE"]
                generator_models = [m for m in models if m["model_type"] == "GENERATOR"]
            else:
                raise StoryProcessException("StoryProcessingService.py", "process_content", "No models found", models_response.get('message'))
            
            # Create API request
            logger.info("Creating API request record")
            request_response = repo.insert_api_request(source_content, threshold_score)
            request_id = request_response.get("data")
            logger.info(f"Created API request with ID: {request_id}")
            
            
            # Get judging categories
            categories_response = repo.get_judging_categories()
            if categories_response["data"]:
                categories = categories_response.get("data")
            else:
                raise StoryProcessException("StoryProcessingService.py", "process_content", "Failed to retrieve judging categories", categories_response.get('message'))
            
            # Process iterations with timing
            logger.info("Starting iteration process")
            iteration_start = time.time()
            result = self.iteration_process(source_content, 2, request_id, threshold_score, judging_models, generator_models, categories)
            iteration_end = time.time()
            result["total_iteration_time"] = round(iteration_end - iteration_start,2)
            
            # Finalize API request
            end_time = time.time()
            execution_time = end_time - start_time
            repo.update_api_request(request_id, result["best_story"], result["best_model_id"], result["best_score"], execution_time)
            
            logger.info(f"Content processing completed successfully for request_id: {request_id}")
            return self.finalize_response(result["best_story"], result["best_score"], result["best_model_name"], result["best_iteration"], result["final_scores"], result["final_comments"], request_id)
            
        except StoryProcessException:
            raise
        except Exception as e:
            raise StoryProcessException("StoryProcessingService.py", "process_content", "Failed to initialize content processing", str(e))
    
    # SQ_NO_1.110- SQ_NO_1.: Iteration Process Loop - initializes variables and starts max 2 iteration loop
    def iteration_process(self, text: str, max_iter: int, request_id: int, threshold_score: float, judging_models: list, generator_models: list, categories: list):
        logger.info(f"Starting iteration process for request_id: {request_id}, max_iterations: {max_iter}")
        try:
            current_text = text
            iteration_count = 0
            best_story = None
            best_score = None
            best_model_id = None
            best_model_name = None
            best_iteration = None
            final_scores = None
            final_comments = None
            
            while iteration_count < max_iter:
                iteration_count += 1
                logger.info(f"Starting iteration {iteration_count}")
                iteration_start_time = time.time()
                
                # Create iteration record
                repo = RepositoryExecute()
                iteration_response = repo.create_iteration(request_id, iteration_count)
                iteration_id = iteration_response.get("data")
                
                # Evaluate content
                judging_service = JudgingService()
                judging_result = judging_service.identify_issue_categories(current_text, categories, judging_models, threshold_score)
                
                # Store judging results (initial content evaluation)
                session_response = repo.insert_judging_session(iteration_id, judging_result.get("scores", {}), judging_result.get("comments", {}))
                if session_response["data"]:
                    session_id = session_response.get("data")
                    # For iteration 1: generative_id = None (judging source content)
                    # For iteration 2+: generative_id = previous iteration's best generative_id
                    generative_id_for_judging = None if iteration_count == 1 else getattr(self, 'previous_best_generative_id', None)
                    repo.insert_judging_results(session_id, judging_result.get("models_data", []), generative_id_for_judging)
                
                issue_categories = judging_result.get("issue_categories", [])
                current_scores = judging_result.get("scores", {})
                
                if len(issue_categories) > 0:
                    logger.info(f"Found {len(issue_categories)} issue categories: {issue_categories}")
                    # Identify preserved categories (scores <= threshold)
                    preserved_categories = [cat["category_name"] for cat in categories if cat["category_name"] not in issue_categories]
                
                    # Generate improved content with both issue and preserved categories
                    generation_service = GenerationService()
                    generation_result = generation_service.multi_generate(generator_models, current_text, issue_categories, preserved_categories, current_scores, threshold_score)
                
                    # Store generated content
                    generative_insert_response = repo.insert_generative_result(iteration_id, generation_result.get("models_data", []))
                    if generative_insert_response["data"]:
                        inserted_records = generative_insert_response.get("data", [])
                        # Add generative_id to generation_result models_data
                        for i, record in enumerate(inserted_records):
                            if i < len(generation_result["models_data"]):
                                generation_result["models_data"][i]["generative_id"] = record["generative_id"]
                
                    # Evaluate generated stories with generative_id tracking
                    analysis_service = AnalysisService()

                    with ThreadPoolExecutor() as executor:
                        futures = [executor.submit(lambda md: (
                            judging_service.identify_issue_categories(md["story"], categories, judging_models, threshold_score),
                            md["generative_id"]
                        ), model_data) for model_data in generation_result["models_data"]]
                    
                        evaluations = []
                        weighted_scores = []
                    
                        for future in futures:
                            eval_result, generative_id = future.result()
                            evaluations.append(eval_result)
                        
                             # Store judging results
                            session_response = repo.insert_judging_session(iteration_id, eval_result.get("scores", {}), eval_result.get("comments", {}))
                            if session_response["data"]:
                                session_id = session_response.get("data")
                                repo.insert_judging_results(session_id, eval_result.get("models_data", []), generative_id)
                        
                            weighted_score = analysis_service.weighted_slope_score(eval_result["scores"])["data"]
                            weighted_scores.append(weighted_score)
                
                    # Update scores
                    score_updates = [{"id": generation_result["models_data"][i]["generative_id"], "score": weighted_scores[i]} for i in range(len(weighted_scores))]
                    repo.update_generative_result(score_updates)
                    
                    # Get model names from database
                    model_names = {m["model_id"]: m["model_name"] for m in generator_models}
                    
                    # Select best story and track generative_id
                    best_index = weighted_scores.index(min(weighted_scores))
                    best_story = generation_result["models_data"][best_index]["story"]
                    best_score = weighted_scores[best_index]
                    best_model_id = generation_result["models_data"][best_index]["model_id"]
                    best_model_name = model_names.get(best_model_id, f"Model {best_model_id}")
                    
                    # Use existing evaluation results from the best story
                    final_scores = evaluations[best_index]["scores"]
                    final_comments = evaluations[best_index]["comments"]
                    self.previous_best_generative_id = generation_result["models_data"][best_index]["generative_id"]
                    
                    best_iteration = iteration_count
                    
                    # Update iteration with best content and timing
                    iteration_end_time = time.time()
                    iteration_execution_time = round(iteration_end_time - iteration_start_time,2)
                    repo.update_iteration(iteration_id, best_story, best_score, json.dumps(issue_categories), iteration_execution_time)
                    current_text = best_story
                    
                    # Check if any categories are still above threshold
                    categories_above_threshold = len([cat for cat, score in final_scores.items() if score > threshold_score])
                    
                    # Stop only if NO categories are above threshold (all categories are acceptable)
                    if categories_above_threshold == 0:
                        logger.info(f"All categories below threshold. Stopping at iteration {iteration_count}")
                        break
                else:
                    logger.info("No issues found in current iteration")
                    # No issues found - update iteration with current content
                    analysis_service = AnalysisService()
                    weighted_score_result = analysis_service.weighted_slope_score(current_scores)
                    
                    best_story = current_text
                    best_score = weighted_score_result["data"]
                    best_iteration = iteration_count
                    final_scores = judging_result.get("scores", {})
                    final_comments = judging_result.get("comments", {})
                    
                    # Update iteration with no issues and timing
                    iteration_end_time = time.time()
                    iteration_execution_time = iteration_end_time - iteration_start_time
                    repo.update_iteration(iteration_id, best_story, best_score, json.dumps([]), iteration_execution_time)
                    break
        
            return {
                "request_id": request_id,
                "best_story": best_story,
                "best_score": best_score,
                "best_model_id": best_model_id,
                "best_model_name": best_model_name,
                "best_iteration": best_iteration,
                "final_scores": final_scores,
                "final_comments": final_comments
            }
        except Exception as e:
            raise
    
    # SQ_NO_1.440 - SQ_NO_1.445: Response Formatting - formats final response with scores, comments, and metadata
    def finalize_response(self, best_story: str, best_score: float, best_model_name: str, best_iteration: str, final_scores: dict, final_comments: dict, request_id: int):
        # For now, return the full JSON response as before
        
        # Format Final_Scores with score and comment for each category
        formatted_scores = {}
        for category, score in final_scores.items():
            formatted_scores[category] = {
                "score": score,
                "comment": final_comments.get(category, "No comment available")
            }
        
        return {
            "request_id": request_id,
            "best_story": best_story,
            "weightedSlopeScore": best_score,
            "from_iteration": best_iteration,
            "generated_model": best_model_name,
            "Final_Scores": formatted_scores
        }