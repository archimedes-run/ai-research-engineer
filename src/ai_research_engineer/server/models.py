from typing import List

from pydantic import BaseModel


class SubmissionRequest(BaseModel):
    name: str
    email: str
    researchTopic: str
    whyInterested: str
    documentsUrls: List[str] = []
    datasetUrl: str = ""
    subscribeToBlog: bool = False


class RunSessionRequest(BaseModel):
    topic: str
    agent_type: str = "adk"
    domain: str = "aiml"
    research_mode: str = "novelty"
    template: str = "NeurReps_2024_Template"
