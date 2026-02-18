import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import logging
from src.DTO.dto import StoryProcessException

logger = logging.getLogger(__name__)

class AnalysisService:
    # SQ_NO_1.354 - SQ_NO_1.363: Generated Content Evaluation - calculates weighted scores for content quality assessment
    def weighted_slope_score(self, scores: dict):
        logger.info(f"Calculating weighted slope score for {len(scores)} categories")
        try:            
            weights = {
                "Repetitive Patterns and Predictability": 1.0,
                "Tone and Human-Like Expression": 2.0,
                "Sentence Structure and Rhythm": 1.5,
                "Punctuation Patterns and Anomalies": 0.5,
                "Specificity and Depth": 2.0,
                "Coherence and Logical Flow": 1.0,
                "Vocabulary Frequency and Overused Language": 1.0,
                "Contextual Awareness and Timeliness": 0.5,
                "Personalization and Voice": 1.5,
                "Factual Accuracy and Logical Validity": 1.0
            }            
            # Create category weights for all categories in scores
            category_weights = {category: weights.get(category, 1.0) for category in scores.keys()}
            weighted_score = round(sum(score * category_weights[category] for category, score in scores.items()) / sum(category_weights.values()),2)
            logger.info(f"Calculated weighted score: {weighted_score}")
            return {"status": 200, "data": weighted_score}
        except Exception as e:
            raise StoryProcessException("AnalysisService.py", "weighted_slope_score", "Failed to calculate weighted score", str(e))