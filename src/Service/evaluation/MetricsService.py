import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import statistics
import logging
from src.DTO.dto import StoryProcessException

logger = logging.getLogger(__name__)

class MetricsService:
    # SQ_NO_1.86 - SQ_NO_1.95: Score Processing & Metrics - combines and averages results from multiple AI models
    def average_scores_and_comments(self, scores_list: list, comments_list: list):
        logger.info(f"Averaging scores from {len(scores_list)} models")
        try:
            averaged_scores = {}
            merged_comments = {}
            
            # Get all unique categories from all models
            all_categories = set()
            for scores in scores_list:
                all_categories.update(scores.keys())
            
            # Average scores for each category
            for category in all_categories:
                values = []
                category_comments = []
                
                
                # Collect scores and comments from all models for this category
                for i, scores in enumerate(scores_list):
                    if category in scores and scores[category] is not None:
                        values.append(scores[category])
                        
                        # Get corresponding comment
                        if i < len(comments_list) and category in comments_list[i]:
                            comment = comments_list[i][category].strip()
                            if comment:
                                category_comments.append(comment)
                
                # Calculate average score
                averaged_scores[category] = round(statistics.mean(values),2) if values else 0
                
                # Merge comments
                if category_comments:
                    merged_comments[category] = " | ".join(category_comments)
                else:
                    merged_comments[category] = "No comment available"
            
            logger.info(f"Averaged scores for {len(averaged_scores)} categories")
            return {"status": 200, "data": {"scores": averaged_scores, "comments": merged_comments}}
        except Exception as e:
            raise StoryProcessException("MetricsService.py", "average_scores_and_comments", "Failed to average scores", str(e))
