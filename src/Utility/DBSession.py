# SQ_NO_1.118 - SQ_NO_1.122: Database Session Dependencies - Import SQLAlchemy and secret manager
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine
from src.DTO.dto import StoryProcessException
from src.secret_manager.secret_manager import get_secret_contents

# SQ_NO_1.124 - SQ_NO_1.128: Database Initialization - Create database engine and session factory
   
try:
        secrets = get_secret_contents()
        connection_string = secrets.get("DB_CONNECTION_STRING")
        if not connection_string:
                raise ValueError("DB_CONNECTION_STRING not found in secrets")
        
        engine = create_engine(connection_string)
        SessionLocal = sessionmaker(bind=engine) 
except Exception as e:
        raise StoryProcessException("DBSession.py", "initialize_database", "Failed to initialize database", str(e))