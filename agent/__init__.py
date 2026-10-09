from agent.models import (
    CareerVector,
    ApplicationStatus,
    ParsedJob,
    JobScoreBreakdown,
    JobAnalysis,
    CoverLetter,
    ResumeCustomization,
    QuestionItem,
    StarBehavioralItem,
    InterviewPrep,
    InterviewDebrief,
    JobApplication
)
from agent.llm import LLMService
from agent.parser import JobParser
from agent.scorer import JobScorer
from agent.analyzer import JobAnalyzer
from agent.cover_letter import CoverLetterGenerator
from agent.resume import ResumeCustomizer
from agent.interview import InterviewAssistant
from agent.job_searcher import JobSearcher, JobSearchResult
from agent.plan import ActionPlanManager
from agent.portfolio import PortfolioManager

class JobAgent:
    """Главный оркестратор AI-агента для поиска работы с интеграцией SuperJob Pro, плана действий и портфолио"""
    def __init__(self):
        self.llm = LLMService()
        self.parser = JobParser(self.llm)
        self.scorer = JobScorer(self.llm)
        self.analyzer = JobAnalyzer(self.llm)
        self.cover_letter = CoverLetterGenerator(self.llm)
        self.resume = ResumeCustomizer(self.llm)
        self.interview = InterviewAssistant(self.llm)
        self.searcher = JobSearcher()
        self.plan = ActionPlanManager()
        self.portfolio = PortfolioManager(self.llm)

__all__ = [
    "JobAgent",
    "CareerVector",
    "ApplicationStatus",
    "ParsedJob",
    "JobScoreBreakdown",
    "JobAnalysis",
    "CoverLetter",
    "ResumeCustomization",
    "QuestionItem",
    "StarBehavioralItem",
    "InterviewPrep",
    "InterviewDebrief",
    "JobApplication",
    "JobParser",
    "JobScorer",
    "JobSearcher",
    "JobSearchResult",
    "ActionPlanManager",
    "PortfolioManager"
]
