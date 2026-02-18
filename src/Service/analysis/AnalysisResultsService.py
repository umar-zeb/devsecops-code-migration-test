# SQ_NO_1.31 - SQ_NO_1.33: Service Dependencies - Import required modules for analysis service
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

# SQ_NO_1.31 - SQ_NO_1.33: Service Dependencies - Import required modules for analysis service
import time
import logging
from src.Repository.repositoryExecute import RepositoryExecute
from src.Service.analysis.AnalysisService import AnalysisService
from src.DTO.dto import StoryProcessException

logger = logging.getLogger(__name__)

class AnalysisResultsService:
    # SQ_NO_1.29-1.194: Main Service Method - Retrieve and process all analysis results for given request_id
    def retrieve_all_results(self, request_id: int):
        logger.info(f"Starting retrieve_all_results for request_id: {request_id}")
        try:
            #  Execution Time Tracking - Start timing for performance measurement
            start_time = time.time()
            #  Repository Instantiation - Create RepositoryExecute instance for database operations
            repo = RepositoryExecute()
            
            #  API Request Retrieval - Get story request data from database
            logger.info("Retrieving API request data")
            api_request_response = repo.get_api_request(request_id)
            if api_request_response["data"] == []:
                raise StoryProcessException("AnalysisResultsService.py", "retrieve_all_results", "No data found for request_id", f"No analysis results found for request_id: {request_id}")

            
            api_request_data = api_request_response.get("data")
            
            #  Iterations Retrieval - Get iteration data and organize by iteration number
            logger.info("Retrieving iterations data")
            iterations_response = repo.get_iterations_by_request_id(request_id)
            if iterations_response["data"] == [] :
                raise StoryProcessException("AnalysisResultsService.py", "retrieve_all_results", "Failed to retrieve iterations", iterations_response.get('message'))
            
            iterations_dict = iterations_response.get("data")
            iterations_by_number = {i['iteration_number']: i for i in iterations_dict}
            iteration_ids = [i['iteration_id'] for i in iterations_dict]
            
             #Judging Sessions Retrieval - Get judging session data for iterations
            logger.info(f"Retrieving judging sessions for {len(iteration_ids)} iterations")
            sessions_response = repo.get_judging_sessions_by_iteration_ids(iteration_ids)
            if sessions_response["data"] == []:
                raise StoryProcessException("AnalysisResultsService.py", "retrieve_all_results", "Failed to retrieve judging sessions", sessions_response.get('message'))
            
            sessions_dict = sessions_response.get("data")
            session_ids = [s['session_id'] for s in sessions_dict]
            
            #  Judging Results Retrieval - Get individual judging results and organize by session
            logger.info(f"Retrieving judging results for {len(session_ids)} sessions")
            judging_results_response = repo.get_judging_results_by_session_ids(session_ids)
            if judging_results_response["data"] == []:
                raise StoryProcessException("AnalysisResultsService.py", "retrieve_all_results", "Failed to retrieve judging results", judging_results_response.get('message'))
            
            results_dict = judging_results_response.get("data")
            judging_results_by_session = {s_id: [r for r in results_dict if r['session_id'] == s_id] for s_id in session_ids}
            
            #  Generative Results Retrieval - Get generated stories and organize by iteration
            logger.info("Retrieving generative results")
            generative_response = repo.get_generative_results_by_iteration_ids(iteration_ids)
            if generative_response["data"] == []:
                raise StoryProcessException("AnalysisResultsService.py", "retrieve_all_results", "Failed to retrieve generative results", generative_response.get('message'))
            
            generative_dict = generative_response.get("data")
            generative_by_iteration = {i_id: [g for g in generative_dict if g['iteration_id'] == i_id] for i_id in iteration_ids}
            model_ids = set([g['model_id'] for g in generative_dict] + [r['model_id'] for r in results_dict])
            
            #  Models Retrieval - Get model information and create name mapping
            models_response = repo.get_models_by_ids(list(model_ids))
            if models_response["data"] == []:
                raise StoryProcessException("AnalysisResultsService.py", "retrieve_all_results", "Failed to retrieve models", models_response.get('message'))
            
            models_dict = models_response.get("data")
            model_map = {m_id: models_dict[m_id]["model_name"] for m_id in models_dict}
            
            #  Response Processing Initialization - Initialize data structures for response building
            text_data = {}
            final_scores = {}
            
            #  Iteration Processing Loop - Process each iteration to build response data
            for iteration_number, iteration_data in iterations_by_number.items():
                iteration_id = iteration_data["iteration_id"]
                iteration_key = f"iteration{'One' if iteration_number==1 else 'Two'}"
                
                # Get judging sessions for this iteration
                iteration_sessions = [s for s in sessions_dict if s['iteration_id'] == iteration_id]
                
                # Get generative results for this iteration
                iteration_generative = generative_by_iteration.get(iteration_id, [])
                
                # Build generative model dict with their corresponding judging results
                generative_model_dict = {}
                
                for gen in iteration_generative:
                    gen_model_name = model_map.get(gen['model_id'], "")
                    gen_key = gen_model_name.lower().replace(" ", "_").replace(".", "_") if gen_model_name else f"model_{gen['model_id']}"
                    generative_id = gen.get('generative_id')
                    
                    # Start building the story data with the generated content
                    story_data = {
                        "story": gen['generated_story'],
                        "execution_time": gen.get('execution_time', 0.0),
                        "weighted_score": gen.get('weighted_score', 0.0)
                    }
                    
                    # Find and add judging results for this specific story
                    judging_results = {}
                    story_merged_scores = {}
                    
                    for session in iteration_sessions:
                        session_results = judging_results_by_session.get(session['session_id'], [])
                        
                        # Find results for this specific generative story
                        story_results = [r for r in session_results if r.get('generative_id') == generative_id]
                        
                        if story_results:
                            # Process judging results for this story
                            for result in story_results:
                                judge_model_name = model_map.get(result['model_id'], f"Model_{result['model_id']}")
                                
                                # Clean up nested scores structure
                                scores = result['judging_response']
                                if isinstance(scores, dict) and 'scores' in scores:
                                    scores = scores['scores']
                                
                                # Transform scores with comments
                                transformed_scores = {}
                                for orig_key, score_val in scores.items():
                                    transformed_scores[orig_key] = {
                                        "score": score_val,
                                        "comment": result['judging_comments'].get(orig_key, "")
                                    }
                                
                                judge_key = judge_model_name.lower().replace(" ", "_").replace(".", "_")
                                judging_results[f"judging_{judge_key}"] = [transformed_scores]
                                judging_results[f"{judge_key}_execution_time"] = result.get('execution_time', 0.0)
                            
                            # Get merged scores for this story from the session
                            if session.get('merged_score') and story_results:
                                # Get category order from judging results
                                first_result = story_results[0]
                                scores = first_result['judging_response']
                                if isinstance(scores, dict) and 'scores' in scores:
                                    scores = scores['scores']
                                category_order = list(scores.keys())
                                
                                # Retrieve merged scores from database with preserved ordering
                                db_merged_scores = session['merged_score']
                                from collections import OrderedDict
                                story_merged_scores = OrderedDict()
                                for category in category_order:
                                    if category in db_merged_scores:
                                        story_merged_scores[category] = round(db_merged_scores[category], 2)
                            break
                    
                    # Add judging results and merged scores to story data
                    story_data.update(judging_results)
                    story_data["mergescore"] = story_merged_scores
                    
                    generative_model_dict[gen_key] = story_data
                
                # Set final scores from the best story across all iterations
                if iteration_number == len(iterations_by_number) or iteration_data.get("iterations_best_weighted_score") == api_request_data.get("best_weighted_score"):
                    # Find the best story's merged scores from generative_model_dict
                    best_story_key = None
                    best_weighted_score = float('inf')
                    
                    for story_key, story_data in generative_model_dict.items():
                        if "weighted_score" in story_data:
                            story_weighted_score = story_data["weighted_score"]
                            if story_weighted_score < best_weighted_score:
                                best_weighted_score = story_weighted_score
                                best_story_key = story_key
                    
                    if best_story_key and best_story_key in generative_model_dict:
                        final_scores = generative_model_dict[best_story_key].get("mergescore", {})
                
                # Add source content section
                iteration_data_dict = {}
                
                if iteration_number == 1:
                    # Add original source content for iteration 1
                    source_content_scores = {}
                    source_merged_scores = {}
                    
                    for session in iteration_sessions:
                        session_results = judging_results_by_session.get(session['session_id'], [])
                        # Find source content evaluation (generative_id is None)
                        source_results = [r for r in session_results if r.get('generative_id') is None]
                        
                        if source_results:
                            for result in source_results:
                                model_name = model_map.get(result['model_id'], f"Model_{result['model_id']}")
                                scores = result['judging_response']
                                if isinstance(scores, dict) and 'scores' in scores:
                                    scores = scores['scores']
                                
                                key = model_name.lower().replace(" ", "_").replace(".", "_")
                                source_content_scores[f"judging_{key}"] = [{
                                    category: {
                                        "score": score_val,
                                        "comment": result['judging_comments'].get(category, "")
                                    } for category, score_val in scores.items()
                                }]
                            
                            if session.get('merged_score') and source_results:
                                first_result = source_results[0]
                                scores = first_result['judging_response']
                                if isinstance(scores, dict) and 'scores' in scores:
                                    scores = scores['scores']
                                category_order = list(scores.keys())
                                
                                db_merged_scores = session['merged_score']
                                from collections import OrderedDict
                                source_merged_scores = OrderedDict()
                                for category in category_order:
                                    if category in db_merged_scores:
                                        source_merged_scores[category] = round(db_merged_scores[category], 2)
                            break
                    
                    source_content_scores["mergescore"] = source_merged_scores
                    
                    # Calculate weighted score for source content
                    analysis_service = AnalysisService()
                    source_weighted_score = analysis_service.weighted_slope_score(source_merged_scores)["data"] if source_merged_scores else 0.0
                    
                    iteration_data_dict["source_content"] = {
                        "content": api_request_data.get("source_content", ""),
                        "judging_results": source_content_scores,
                        "weighted_score": round(source_weighted_score, 2)
                    }
                
                elif iteration_number == 2:
                    # Add best story from iteration 1 as source content for iteration 2
                    prev_iteration = iterations_by_number.get(1)
                    if prev_iteration:
                        source_content_scores = {}
                        source_merged_scores = {}
                        
                        # Find the best story from iteration 1 in the generative results
                        prev_iteration_id = prev_iteration['iteration_id']
                        prev_generative = generative_by_iteration.get(prev_iteration_id, [])
                        
                        # Find the best generative_id from iteration 1
                        best_generative_id = None
                        best_score = float('inf')
                        for gen in prev_generative:
                            if gen.get('weighted_score', float('inf')) < best_score:
                                best_score = gen.get('weighted_score', float('inf'))
                                best_generative_id = gen.get('generative_id')
                        
                        # Now find judging results for this best story in iteration 2's sessions
                        for session in iteration_sessions:
                            session_results = judging_results_by_session.get(session['session_id'], [])
                            # Find source content evaluation (generative_id matches the best story from iteration 1)
                            source_results = [r for r in session_results if r.get('generative_id') == best_generative_id]
                            
                            if source_results:
                                for result in source_results:
                                    model_name = model_map.get(result['model_id'], f"Model_{result['model_id']}")
                                    scores = result['judging_response']
                                    if isinstance(scores, dict) and 'scores' in scores:
                                        scores = scores['scores']
                                    
                                    key = model_name.lower().replace(" ", "_").replace(".", "_")
                                    source_content_scores[f"judging_{key}"] = [{
                                        category: {
                                            "score": score_val,
                                            "comment": result['judging_comments'].get(category, "")
                                        } for category, score_val in scores.items()
                                    }]
                                
                                if session.get('merged_score') and source_results:
                                    first_result = source_results[0]
                                    scores = first_result['judging_response']
                                    if isinstance(scores, dict) and 'scores' in scores:
                                        scores = scores['scores']
                                    category_order = list(scores.keys())
                                    
                                    db_merged_scores = session['merged_score']
                                    from collections import OrderedDict
                                    source_merged_scores = OrderedDict()
                                    for category in category_order:
                                        if category in db_merged_scores:
                                            source_merged_scores[category] = round(db_merged_scores[category], 2)
                                break
                        
                        source_content_scores["mergescore"] = source_merged_scores
                        
                        # Calculate weighted score for source content
                        analysis_service = AnalysisService()
                        source_weighted_score = analysis_service.weighted_slope_score(source_merged_scores)["data"] if source_merged_scores else 0.0
                        
                        iteration_data_dict["source_content"] = {
                            "content": prev_iteration.get("best_story", ""),
                            "judging_results": source_content_scores,
                            "weighted_score": round(source_weighted_score, 2)
                        }
                
                # Add other data - only include generative_model if it has content
                iteration_data_dict["iteration_execution_time"] = iteration_data.get('execution_time', 0.0)
                if generative_model_dict:
                    iteration_data_dict["generative_model"] = generative_model_dict
                
                text_data[iteration_key] = iteration_data_dict
            
            best_story = api_request_data.get("best_story", "")
            
            # Determine actual models used from database
            best_generated_model = None
            
            # Get best generated model from stored generated_model_id
            best_generated_model_id = api_request_data.get("generated_model_id")
            if best_generated_model_id:
                best_generated_model = model_map.get(best_generated_model_id, "Unknown Model")
            
            # If final_scores is empty, use the source content scores from the last iteration
            if not final_scores:
                last_iteration_key = f"iteration{'One' if len(iterations_by_number) == 1 else 'Two'}"
                if last_iteration_key in text_data and "source_content" in text_data[last_iteration_key]:
                    source_judging = text_data[last_iteration_key]["source_content"].get("judging_results", {})
                    final_scores = source_judging.get("mergescore", {})
            
            # Build final response structure
            response_structure = {
                "best_story": best_story,
                "weightedSlopeScore": round(api_request_data.get("best_weighted_score", 0.0), 2),
                "from_iteration": str(len(iterations_by_number)),
                "generated_model": best_generated_model, 
                "Final_Scores": final_scores,
                "text_data": text_data,
                "api_execution_time": api_request_data.get("execution_time", 0.0)
            }
            
            return {
                "status": 200,
                "data": response_structure
            }
            
        #  Service Exception Handling - Handle and re-raise exceptions with proper error context
        except StoryProcessException:
            raise
        except Exception as e:
            raise StoryProcessException("AnalysisResultsService.py", "retrieve_all_results", "Failed to retrieve analysis results", str(e))