from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Models(Base):
    __tablename__ = 'models'
    
    model_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    model_type = Column(Text, nullable=False)
    version = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

class JudgingCategory(Base):
    __tablename__ = 'judging_category'
    
    category_id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(Text, nullable=False)
    description = Column(Text)
    evaluation_criteria = Column(Text)
    is_active = Column(Boolean, default=True)

class StoryRequest(Base):
    __tablename__ = 'story_request'
    
    request_id = Column(Integer, primary_key=True, autoincrement=True)
    source_content = Column(Text, nullable=False)
    threshold_score = Column(Float)
    best_story = Column(Text)
    generated_model_id = Column(Integer, ForeignKey('models.model_id'))
    best_weighted_score = Column(Float)
    execution_time = Column(Float)
    created_at = Column(DateTime)

class Iteration(Base):
    __tablename__ = 'iteration'
    
    iteration_id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey('story_request.request_id'))
    iteration_number = Column(Integer, nullable=False)
    iterations_best_story = Column(Text)
    iterations_best_weighted_score = Column(Float)
    execution_time = Column(Float)
    issues = Column(JSON)
    created_at = Column(DateTime)

class JudgingSession(Base):
    __tablename__ = 'judging_session'
    
    session_id = Column(Integer, primary_key=True, autoincrement=True)
    iteration_id = Column(Integer, ForeignKey('iteration.iteration_id'))
    merged_score = Column(JSON)
    created_at = Column(DateTime)

class GenerativeResult(Base):
    __tablename__ = 'generative_result'
    
    generative_id = Column(Integer, primary_key=True, autoincrement=True)
    iteration_id = Column(Integer, ForeignKey('iteration.iteration_id'))
    model_id = Column(Integer, ForeignKey('models.model_id'))
    input_token = Column(Integer)
    output_token = Column(Integer)
    generative_response = Column(JSON)
    generative_response_time = Column(Float)
    weighted_scores = Column(Float)
    created_at = Column(DateTime)

class JudgingResult(Base):
    __tablename__ = 'judging_result'
    
    judging_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('judging_session.session_id'))
    generative_id = Column(Integer, ForeignKey('generative_result.generative_id'))
    model_id = Column(Integer, ForeignKey('models.model_id'))
    input_token = Column(Integer)
    output_token = Column(Integer)
    judging_response = Column(JSON)
    judging_response_time = Column(Float)
    created_at = Column(DateTime)

class ErrorLog(Base):
    __tablename__ = 'error_log'
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    error_filename = Column(Text)
    error_function = Column(Text)
    log_message = Column(String(100))
    timestamp = Column(DateTime)
    error_details = Column(String(100))