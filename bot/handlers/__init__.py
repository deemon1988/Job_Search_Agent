from bot.handlers.vacancies import router as vacancies_router
from bot.handlers.tracker import router as tracker_router
from bot.handlers.interview import router as interview_router
from bot.handlers.search import router as search_router

__all__ = ["vacancies_router", "tracker_router", "interview_router", "search_router"]
