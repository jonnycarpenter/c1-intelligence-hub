"""FMP Premium News Collector

Collects premium financial news from FMP (Financial Modeling Prep).
Sources include: Benzinga, Seeking Alpha, Bloomberg, WSJ, etc.

Data Type: premium_news
"""

from .collector import FMPNewsCollector
from .client import FMPNewsClient
from .models import FMPNewsArticle

__all__ = ["FMPNewsCollector", "FMPNewsClient", "FMPNewsArticle"]
