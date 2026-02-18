# SQ_NO_1.4 - SQ_NO_1.6: Controller Dependencies - Import required modules for analysis controller
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import json
import logging
from src.Service.analysis.AnalysisResultsService import AnalysisResultsService
from src.DTO.dto import StatusCode, StoryProcessException

logger = logging.getLogger(__name__)

class AnalysisResultsController:
    # SQ_NO_1.22-1.190: Analysis Controller Method - Main controller method for handling analysis requests
    def analysis_controller(self, path: str, method: str, params: dict, user_context=None):
        logger.info(f"Analysis controller started with params: {params}")
        try:
            #  Parameter Validation - Extract and validate request_id parameter
            request_id = params.get('request_id')
            
            #  Required Parameter Check - Validate request_id is provided
            if request_id is None:
               return{"status_code":400, "message":"Missing required  request_id"}
            
            #  Parameter Type Validation - Convert request_id to integer
            try:
                validated_id = int(request_id)
            except ValueError as e:
                return{"status_code":400, "message":"Invalid request_id format""Invalid request_id format"}
            
            #  Service Instantiation - Create AnalysisResultsService instance
            analysis_service = AnalysisResultsService()
            #  Service Method Call - Invoke retrieve_all_results with validated request_id
            logger.info(f"Calling retrieve_all_results for request_id: {validated_id}")
            final_response = analysis_service.retrieve_all_results(validated_id)
            logger.info("Analysis results retrieved successfully")
            
            #  Success Response Formation - Format successful controller response
            return {
                "statusCode": 200,
                "body": json.dumps(final_response),
                "headers": {"Content-Type": "application/json"}
            }
            
        #  Exception Handling - Handle various error scenarios with appropriate HTTP status codes
        except Exception as e:
            logger.error(f"Error in analysis_controller: {str(e)}")
            if isinstance(e, StoryProcessException):
                try:
                    from src.Repository.repositoryExecute import RepositoryExecute
                    repo = RepositoryExecute()
                    repo.insert_error_log(e.error_filename, e.error_function, e.log_message, e.error_details)
                except:
                    pass
                return {
                    "statusCode": 400,
                    "body": json.dumps({"message": f"Error in {e.error_function} for file {e.error_filename}: {e.log_message}"}),
                    "headers": {"Content-Type": "application/json"}
                }
            else:
                try:
                    from src.Repository.repositoryExecute import RepositoryExecute
                    repo = RepositoryExecute()
                    repo.insert_error_log("AnalysisResultsController.py", "analysis_controller", "Unexpected error", str(e))
                except:
                    pass
                return {
                    "statusCode": 500,
                    "body": json.dumps({"message": f"Unexpected error: {str(e)}"}),
                    "headers": {"Content-Type": "application/json"}
                }
            