# Unified Lambda Handler - Routes requests based on HTTP method and path
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ''))

import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

from src.Controller.ContentProcessController import ContentProcessController
from src.Controller.AnalysisResultsController import AnalysisResultsController

def lambda_handler(event, context):
    logger.info(f"Lambda handler started with method: {event.get('requestContext', {}).get('http', {}).get('method')} and path: {event.get('requestContext', {}).get('http', {}).get('path')}")
    
    try:
        path = event["requestContext"]["http"]["path"]
        method = event["requestContext"]["http"]["method"]
        
        if method == "POST" and "/story_regenerate" in path:
            # Parse body for Lambda Function URL
            if 'body' in event:
                params = json.loads(event['body'])
            else:
                params = event.get('params', {})
            
            logger.info("Processing story request")
            controller = ContentProcessController()
            result = controller.story_controller(path, method, params)
            logger.info("Story request processed successfully")
            
            # Check if result contains status_code for error responses
            if isinstance(result, dict) and 'status_code' in result:
                return {
                    'statusCode': result['status_code'],
                    'body': json.dumps({'message': result.get('message', 'Error occurred')})
                }
            
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
        elif method == "GET" and "/get_analysis_result" in path:
            params = event.get('queryStringParameters') or {}
            request_id = params.get('request_id', None)
            logger.info(f"Processing analysis request for request_id: {request_id}")
            controller = AnalysisResultsController()
            result = controller.analysis_controller(path, method, {"request_id": request_id})
            logger.info("Analysis request processed successfully")
            return {
                'statusCode': result['statusCode'],
                'body': result['body'],
                'headers': result.get('headers', {})
            }
        else:
            logger.error(f"Unsupported method {method} or path {path}")
            raise Exception(f"Unsupported method {method} or path {path}")
            
    except Exception as e:
        logger.error(f"Exception in lambda_handler: {str(e)}")
        print(f" Exception in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)}),
            'headers': {'Content-Type': 'application/json'}
        }
    
    