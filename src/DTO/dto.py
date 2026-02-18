from datetime import datetime


# SQ_NO_1.448 - SQ_NO_1.450: API Request Finalization - finalizes story_request with best results and total execution time

class StatusCode:
    SUCCESS = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    INTERNAL_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503

class StoryProcessException(Exception):
    def __init__(self, error_filename, error_function, log_message, error_details):
        self.error_filename = error_filename
        self.error_function = error_function
        self.log_message = log_message
        self.error_details = error_details
        self.timestamp = datetime.now()
        
        super().__init__(f"{log_message} in {error_function} ({error_filename})")
