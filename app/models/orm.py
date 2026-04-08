from sqlalchemy import Column, String, Float, JSON, ForeignKey
from app.database import Base

class JobModel(Base):
    __tablename__ = "jobs"
    job_id = Column(String, primary_key=True, index=True)
    title = Column(String)
    data = Column(JSON)

class CandidateModel(Base):
    __tablename__ = "candidates"
    candidate_id = Column(String, primary_key=True, index=True)
    name = Column(String)
    data = Column(JSON)

class ScreeningResultModel(Base):
    __tablename__ = "screenings"
    id = Column(String, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.job_id"))
    candidate_id = Column(String, ForeignKey("candidates.candidate_id"))
    overall_score = Column(Float)
    status = Column(String)
    data = Column(JSON)

class ChatbotSessionModel(Base):
    __tablename__ = "chatbot_sessions"
    session_id = Column(String, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.job_id"))
    candidate_id = Column(String, ForeignKey("candidates.candidate_id"))
    status = Column(String)
    data = Column(JSON)
