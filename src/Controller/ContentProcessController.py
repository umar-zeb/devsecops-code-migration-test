
# SQ_NO_1.4 - SQ_NO_1.6:  import required packages for controller 
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import logging
from src.Service.StoryProcessingService import StoryProcessingService
from src.DTO.dto import StatusCode, StoryProcessException

logger = logging.getLogger(__name__)

class ContentProcessController:
    # SQ_NO_1.44 - SQ_NO_1.460:  Controller - handles HTTP requests, initializes StoryProcessingService with exception handling
    def story_controller(self, path, method, params):
        logger.info(f"Story controller started with path: {path}, method: {method}")
        try:
            story_service = StoryProcessingService()
            logger.info("Starting story processing")
            result = story_service.process_content(params)
            logger.info("Story processing completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error in story_controller: {str(e)}")
            if isinstance(e, StoryProcessException):
                try:
                    from src.Repository.repositoryExecute import RepositoryExecute
                    repo = RepositoryExecute()
                    repo.insert_error_log(e.error_filename, e.error_function, e.log_message, e.error_details)
                except:
                    pass
                return {
                    "status": StatusCode.BAD_REQUEST,
                    "message": f"Error in {e.error_function} for file {e.error_filename}: {e.log_message}"
                }
            else:
                try:
                    from src.Repository.repositoryExecute import RepositoryExecute
                    repo = RepositoryExecute()
                    repo.insert_error_log("ContentProcessController.py", "story_controller", "Unexpected error", str(e))
                except:
                    pass
                return {
                    "status": StatusCode.INTERNAL_ERROR,
                    "message": f"Unexpected error: {str(e)}"
                }