
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Set
from app.config.settings import settings
from app.utils.date_extraction import extract_publication_date
from .exa_client import ExaClient
from .models import PressRelease

logger = logging.getLogger(__name__)

class PressReleaseCollector:
    def __init__(self, exa_client: ExaClient = None, existing_urls: Set[str] = None):
        self.client = exa_client or ExaClient()
        self.existing_urls = existing_urls or set()
    
    def build_search_query(self, company_name: str, ticker: str = None) -> str:
        if ticker:
            return f'"{company_name}" OR "{ticker}"'
        return f'"{company_name}"'
    
    def collect_for_company(self, company_id: str, company_name: str, ticker: str = None, limit: int = None, num_days: int = None) -> List[PressRelease]:
        query = self.build_search_query(company_name, ticker)
        
        max_results = limit or settings.pr_max_results
        
        try:
            search_results = self.client.search(
                query=query,
                max_results=max_results,
                search_depth=settings.pr_search_depth,
                include_domains=settings.pr_sources,
                num_days=num_days
            )
        except Exception as e:
            logger.error(f"Search failed for {company_name}: {e}")
            return []
        
        press_releases = []
        for result in search_results:
            if result.url in self.existing_urls:
                continue
            
            try:
                full_text = self.client.extract(result.url)
            except Exception as e:
                logger.error(f"Extraction failed for {result.url}: {e}")
                continue
            
            if not full_text:
                continue
            
            source = "unknown"
            if "prnewswire" in result.url: source = "prnewswire"
            elif "businesswire" in result.url: source = "businesswire"
            elif "globenewswire" in result.url: source = "globenewswire"
            
            # Exa provides clean publishedDate - use it directly when available
            # Fall back to extract_publication_date only if Exa date is missing
            # IMPORTANT: Validate dates are not in the future (Exa sometimes extracts 
            # future projection dates from content)
            discovered_at = datetime.utcnow()
            max_future_days = 2  # Allow small buffer for timezone differences
            
            if result.published_date:
                # Exa returns ISO format dates - parse them
                try:
                    if isinstance(result.published_date, str):
                        # Handle ISO format: "2025-01-15T00:00:00.000Z"
                        published_at = datetime.fromisoformat(result.published_date.replace('Z', '+00:00'))
                    else:
                        published_at = result.published_date
                    
                    # Validate: reject future dates (Exa sometimes returns these incorrectly)
                    if published_at:
                        # Make naive for comparison
                        if hasattr(published_at, 'tzinfo') and published_at.tzinfo is not None:
                            check_date = published_at.replace(tzinfo=None)
                        else:
                            check_date = published_at
                        max_valid_date = datetime.utcnow() + timedelta(days=max_future_days)
                        if check_date > max_valid_date:
                            logger.debug(
                                f"Rejecting future date {published_at} from Exa for {result.url[:60]}... "
                                f"(likely a market projection date)"
                            )
                            published_at = None
                except Exception:
                    published_at = extract_publication_date(
                        url=result.url,
                        content=full_text,
                        api_date=result.published_date,
                        fallback=None
                    )
            else:
                # Fallback to extraction if Exa didn't provide date
                published_at = extract_publication_date(
                    url=result.url,
                    content=full_text,
                    api_date=None,
                    fallback=None
                )

            pr = PressRelease(
                id=str(uuid.uuid4()),
                company_id=company_id,
                company_name=company_name,
                ticker=ticker,
                title=result.title,
                url=result.url,
                source=source,
                published_date=published_at,
                full_text=full_text,
                discovered_at=discovered_at,  # Use same timestamp for consistency
                word_count=len(full_text.split())
            )
            press_releases.append(pr)
            self.existing_urls.add(result.url)
            
        return press_releases
    
    def collect_batch(self, companies: List[dict], limit: int = None, num_days: int = None) -> List[PressRelease]:
        all_releases = []
        for company in companies:
            releases = self.collect_for_company(
                company_id=company["id"],
                company_name=company["name"],
                ticker=company.get("ticker"),
                limit=limit,
                num_days=num_days
            )
            all_releases.extend(releases)
        return all_releases
