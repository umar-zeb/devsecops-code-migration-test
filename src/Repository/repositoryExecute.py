# SQ_NO_1.69 - SQ_NO_1.77: Repository Dependencies - Import database and utility modules for data access
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from src.Repository.Schema import Models, JudgingCategory, StoryRequest, Iteration, JudgingSession, JudgingResult, GenerativeResult, ErrorLog
from src.Utility.DBSession import SessionLocal
from src.DTO.dto import StoryProcessException
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class RepositoryExecute:
    
    # SQ_NO_1.57 - SQ_NO_1.77: Database Models Retrieval - retrieves active JUDGE and GENERATOR models from database with session management
    def get_models(self):
        logger.info("Retrieving active models from database")
        try:
            with SessionLocal() as session:
                query = session.query(Models).filter(Models.is_active == True).filter(Models.model_type.in_(["JUDGE", "GENERATOR"]))
                models = query.all()
                models_dict = [{"model_id": m.model_id, "model_name": m.name, "model_type": m.model_type, "is_active": m.is_active} for m in models]
                return {"status": 200, "data": models_dict}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "get_models", "Failed to retrieve models", str(e))
    
    # SQ_NO_1.83- SQ_NO_1.94: Story Request Creation - creates initial story_request record with source content and threshold
    def insert_api_request(self, source_content: str, threshold_score: float):
        logger.info(f"Creating API request with threshold_score: {threshold_score}")
        try:
            with SessionLocal() as session:
                story_request = StoryRequest(source_content=source_content, threshold_score=threshold_score, created_at=datetime.now())
                session.add(story_request)
                session.commit()
                session.refresh(story_request)
                return {"status": 200, "data": story_request.request_id}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "insert_api_request", "Failed to insert API request", str(e))
    
    # SQ_NO_1.97 - SQ_NO_1.107: Judging Categories Retrieval - fetches active evaluation categories for content assessment
    def get_judging_categories(self):
        logger.info("Retrieving active judging categories")
        try:
            with SessionLocal() as session:
                query = session.query(JudgingCategory).filter(JudgingCategory.is_active == True)
                categories = query.all()
                categories_dict = [{"category_id": c.category_id, "category_name": c.category_name, "description": c.description, "evaluation_criteria": c.evaluation_criteria} for c in categories]
                return {"status": 200, "data": categories_dict}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "get_judging_categories", "Failed to retrieve judging categories", str(e))
    
    # SQ_NO_1.123 - SQ_NO_1.134: Iteration Record Creation - creates iteration record for tracking each processing cycle
    def create_iteration(self, request_id: int, iteration_number: int):
        logger.info(f"Creating iteration {iteration_number} for request_id: {request_id}")
        try:
            with SessionLocal() as session:
                iteration = Iteration(request_id=request_id, iteration_number=iteration_number, created_at=datetime.now())
                session.add(iteration)
                session.commit()
                session.refresh(iteration)
                return {"status": 200, "data": iteration.iteration_id}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "create_iteration", "Failed to create iteration record", str(e))
    
    # SQ_NO_1.227 - SQ_NO_1.243: Judging Results Storage - stores evaluation data with session management
    def insert_judging_session(self, iteration_id: int, merged_score: dict, merged_comments: dict):
        logger.info(f"Inserting judging session for iteration_id: {iteration_id}")
        try:
            with SessionLocal() as session:
                judging_session = JudgingSession(
                    iteration_id=iteration_id,
                    merged_score=merged_score,
                    created_at=datetime.now()
                )
                session.add(judging_session)
                session.commit()
                session.refresh(judging_session)
                return {"status": 200, "data": judging_session.session_id}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "insert_judging_session", "Failed to insert judging session", str(e))
    
    # SQ_NO_1.244 - SQ_NO_1.260: Judging Results Storage - stores individual judge results with bulk operations
    def insert_judging_results(self, session_id: int, models_data: list, generative_id: int = None):
        logger.info(f"Inserting {len(models_data)} judging results for session_id: {session_id}")
        try:
            with SessionLocal() as session:
                records = []
                for model_data in models_data:
                    records.append({
                        "session_id": session_id,
                        "generative_id": generative_id,
                        "model_id": model_data["model_id"],
                        "input_token": model_data["input_tokens"],
                        "output_token": model_data["output_tokens"],
                        "judging_response": json.dumps({"scores": model_data["scores"], "comments": model_data["comments"]}),
                        "judging_response_time": model_data.get("execution_time", 0.0),
                        "created_at": datetime.now()
                    })
                session.bulk_insert_mappings(JudgingResult, records)
                session.commit()
                return {"status": 200, "data": "Records inserted"}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "insert_judging_results", "Failed to insert judging results", str(e))
    
    # SQ_NO_1.331 - SQ_NO_1.346: Generative Results Storage - stores generated content with individual session.add() calls to capture IDs
    def insert_generative_result(self, iteration_id: int, models_data: list):
        logger.info(f"Inserting {len(models_data)} generative results for iteration_id: {iteration_id}")
        try:
            with SessionLocal() as session:
                inserted_records = []
                for model_data in models_data:
                    generative_result = GenerativeResult(
                        iteration_id=iteration_id,
                        model_id=model_data["model_id"],
                        input_token=model_data["input_tokens"],
                        output_token=model_data["output_tokens"],
                        generative_response=json.dumps({"story": model_data["story"]}),
                        generative_response_time=model_data.get("execution_time", 0.0),
                        created_at=datetime.now()
                    )
                    session.add(generative_result)
                    session.flush()  # Get the ID without committing
                    inserted_records.append({
                        "generative_id": generative_result.generative_id,
                        "model_id": model_data["model_id"],
                        "story": model_data["story"]
                    })
                session.commit()
                return {"status": 200, "data": inserted_records}
        except Exception as e:
            print(f"Error in insert_generative_result: {str(e)}")
            print(f"Models data: {models_data}")
            import traceback
            traceback.print_exc()
            raise StoryProcessException("repositoryExecute.py", "insert_generative_result", "Failed to insert generative results", str(e))
    
    # SQ_NO_1.1364 - SQ_NO_1.375: Score Updates & Best Selection - updates weighted scores for generated content
    def update_generative_result(self, updates: list):
        logger.info(f"Updating {len(updates)} generative results with weighted scores")
        try:
            with SessionLocal() as session:
                for update in updates:
                    result = session.query(GenerativeResult).filter(GenerativeResult.generative_id == update["id"]).first()
                    result.weighted_scores = update["score"]
                session.commit()
                return {"status": 200, "message": "Records updated"}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "update_generative_result", "Failed to update generative results", str(e))
    
    # SQ_NO_1.393 - SQ_NO_1.407: Iteration Updates - stores best content and execution metrics for current iteration
    def update_iteration(self, iteration_id: int, best_story: str, best_score: float, issues: str, execution_time: float = None):
        try:
            with SessionLocal() as session:
                iteration = session.query(Iteration).filter(Iteration.iteration_id == iteration_id).first()
                iteration.iterations_best_story = best_story
                iteration.iterations_best_weighted_score = best_score
                iteration.issues = issues
                iteration.execution_time = execution_time
                session.commit()
                return {"status": 200, "message": "Iteration updated"}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "update_iteration", "Failed to update iteration", str(e))
    
    # SQ_NO_1.423 - SQ_NO_1.438: API Request Finalization - finalizes story_request with best results and total execution time
    def update_api_request(self, request_id: int, best_story: str, best_model_id: int, best_score: float, execution_time: float):
        try:
            with SessionLocal() as session:
                story_request = session.query(StoryRequest).filter(StoryRequest.request_id == request_id).first()
                story_request.best_story = best_story
                story_request.generated_model_id = best_model_id
                story_request.best_weighted_score = best_score
                story_request.execution_time = execution_time
                session.commit()
                return {"status": 200, "message": "API request updated"}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "update_api_request", "Failed to update API request", str(e))
       
       
     # SQ_NO_1.451 - SQ_NO_1.459: API Request Finalization - Error log all error message with coresponding file 

    def insert_error_log(self, error_filename: str, error_function: str, log_message: str, error_details: str):
        try:
            with SessionLocal() as session:
                error_log = ErrorLog(
                    error_filename=error_filename,
                    error_function=error_function,
                    log_message=log_message,
                    timestamp=datetime.now(),
                    error_details=error_details
                )
                session.add(error_log)
                session.commit()
        except:
            pass  # Silent fail for error logging
    

    # SQ_NO_1.33 - SQ_NO_1.54: API Request Retrieval - Get story request data from database by request_id
    def get_api_request(self, request_id: int):
        try:
            with SessionLocal() as session:
                query = session.query(StoryRequest).filter(StoryRequest.request_id == request_id)
                api_request = query.first()
                
                if api_request is not None:
                    api_request_dict = {
                        "source_content": api_request.source_content,
                        "threshold_score": api_request.threshold_score,
                        "best_story": api_request.best_story,
                        "best_weighted_score": api_request.best_weighted_score,
                        "execution_time": api_request.execution_time,
                        "generated_model_id": api_request.generated_model_id
                    }
                    return {"status": 200, "data": api_request_dict}
                else:
                    raise StoryProcessException("repositoryExecute.py", "get_api_request", f"API Request with id {request_id} not found", "Resource not found")
        except StoryProcessException:
            raise
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "get_api_request", f"Failed to retrieve API request with id {request_id}", str(e))
    
    # SQ_NO_1.55 - SQ_NO_1.69: Iterations Retrieval - Get all iterations for a request ordered by iteration number
    def get_iterations_by_request_id(self, request_id: int):
        try:
            with SessionLocal() as session:
                query = session.query(Iteration).filter(Iteration.request_id == request_id).order_by(Iteration.iteration_number)
                iterations = query.all()
                iterations_dict = [{
                    "iteration_id": iter.iteration_id,
                    "iteration_number": iter.iteration_number,
                    "best_story": iter.iterations_best_story,
                    "best_weighted_score": iter.iterations_best_weighted_score,
                    "issues": iter.issues,
                    "execution_time": iter.execution_time
                } for iter in iterations]
                return {"status": 200, "data": iterations_dict}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "get_iterations_by_request_id", f"Failed to retrieve iterations for request {request_id}", str(e))
    
    # SQ_NO_1.70 - SQ_NO_1.83: Judging Sessions Retrieval - Get judging sessions for multiple iterations
    def get_judging_sessions_by_iteration_ids(self, iteration_ids: list):
        try:
            with SessionLocal() as session:
                query = session.query(JudgingSession).filter(JudgingSession.iteration_id.in_(iteration_ids))
                sessions = query.all()
                sessions_dict = [{
                    "session_id": s.session_id,
                    "iteration_id": s.iteration_id,
                    "merged_score": s.merged_score,
                    "merged_comments": {}
                } for s in sessions]
                return {"status": 200, "data": sessions_dict}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "get_judging_sessions_by_iteration_ids", "Failed to retrieve judging sessions", str(e))
    
    # SQ_NO_1.84 - SQ_NO_1.97: Judging Results Retrieval - Get individual judging results for sessions
    def get_judging_results_by_session_ids(self, session_ids: list):
        try:
            with SessionLocal() as session:
                query = session.query(JudgingResult).filter(JudgingResult.session_id.in_(session_ids))
                results = query.all()
                results_dict = []
                for r in results:
                    judging_data = json.loads(r.judging_response) if r.judging_response else {}
                    results_dict.append({
                        "result_id": r.judging_id,
                        "session_id": r.session_id,
                        "generative_id": r.generative_id,
                        "model_id": r.model_id,
                        "judging_response": judging_data,
                        "judging_comments": judging_data.get("comments", {}),
                        "input_token": r.input_token,
                        "output_token": r.output_token,
                        "execution_time": r.judging_response_time
                    })
                return {"status": 200, "data": results_dict}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "get_judging_results_by_session_ids", "Failed to retrieve judging results", str(e))
    
    # SQ_NO_1.98 - SQ_NO_1.111: Generative Results Retrieval - Get generated stories and scores for iterations
    def get_generative_results_by_iteration_ids(self, iteration_ids: list):
        try:
            with SessionLocal() as session:
                query = session.query(GenerativeResult).filter(GenerativeResult.iteration_id.in_(iteration_ids))
                generative_results = query.all()
                generative_dict = [{
                    "generative_id": g.generative_id,
                    "iteration_id": g.iteration_id,
                    "model_id": g.model_id,
                    "generated_story": json.loads(g.generative_response).get("story", ""),
                    "weighted_score": g.weighted_scores,
                    "input_token": g.input_token,
                    "output_token": g.output_token,
                    "execution_time": g.generative_response_time
                } for g in generative_results]
                return {"status": 200, "data": generative_dict}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "get_generative_results_by_iteration_ids", "Failed to retrieve generative results", str(e))
    
    # SQ_NO_1.112 - SQ_NO_1.125: Models Retrieval - Get model information by model IDs
    def get_models_by_ids(self, model_ids: list):
        try:
            with SessionLocal() as session:
                query = session.query(Models).filter(Models.model_id.in_(model_ids))
                models = query.all()
                models_dict = {m.model_id: {
                    "model_id": m.model_id,
                    "model_name": m.name,
                    "model_type": m.model_type
                } for m in models}
                return {"status": 200, "data": models_dict}
        except Exception as e:
            raise StoryProcessException("repositoryExecute.py", "get_models_by_ids", "Failed to retrieve models", str(e))