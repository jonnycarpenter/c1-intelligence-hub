"""
Pipeline Company Filters - Post-enrichment filtering for search results.

This module provides structured filtering of Apollo-enriched company data,
enabling the Pipeline agent to apply user-specified criteria AFTER semantic
search and enrichment (ensuring high-quality filter data).

Flow:
1. Exa semantic search finds relevant companies
2. Apollo enrichment adds firmographics (revenue, employees, location, etc.)
3. This module filters enriched results based on user criteria
4. Agent receives filter metadata to provide smart feedback

Supported Filters (MVP):
- Revenue: min/max annual revenue
- Employees: min/max employee count
- Geography: states, countries
- Industry: industry string matching

Future Filters:
- Technologies: required tech stack
- Keywords: required keyword tags
- Founded year: min/max year
- SIC/NAICS codes
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CompanyFilters:
    """
    Structured filter criteria for company search results.
    
    All filters are optional. Only non-None filters are applied.
    Multiple filters use AND logic (company must pass all).
    """
    # Revenue filters (in USD)
    min_revenue: Optional[int] = None  # e.g., 50000000 for $50M+
    max_revenue: Optional[int] = None  # e.g., 100000000 for <$100M
    
    # Employee count filters
    min_employees: Optional[int] = None  # e.g., 200
    max_employees: Optional[int] = None  # e.g., 500
    
    # Geography filters (case-insensitive matching)
    states: Optional[List[str]] = None  # e.g., ["Florida", "California"]
    countries: Optional[List[str]] = None  # e.g., ["United States", "Canada"]
    cities: Optional[List[str]] = None  # e.g., ["Phoenix", "Miami"]
    
    # Industry filter (substring match, case-insensitive)
    industries: Optional[List[str]] = None  # e.g., ["Manufacturing", "Aerospace"]
    
    # Future filters (not yet implemented)
    required_technologies: Optional[List[str]] = None
    required_keywords: Optional[List[str]] = None
    min_founded_year: Optional[int] = None
    max_founded_year: Optional[int] = None
    
    def is_empty(self) -> bool:
        """Check if no filters are set."""
        return all([
            self.min_revenue is None,
            self.max_revenue is None,
            self.min_employees is None,
            self.max_employees is None,
            self.states is None,
            self.countries is None,
            self.cities is None,
            self.industries is None,
            self.required_technologies is None,
            self.required_keywords is None,
            self.min_founded_year is None,
            self.max_founded_year is None,
        ])
    
    def to_description(self) -> str:
        """Generate human-readable description of active filters."""
        parts = []
        
        if self.min_revenue is not None:
            parts.append(f"revenue ≥ ${self.min_revenue:,}")
        if self.max_revenue is not None:
            parts.append(f"revenue ≤ ${self.max_revenue:,}")
        if self.min_employees is not None:
            parts.append(f"employees ≥ {self.min_employees:,}")
        if self.max_employees is not None:
            parts.append(f"employees ≤ {self.max_employees:,}")
        if self.states:
            parts.append(f"states: {', '.join(self.states)}")
        if self.countries:
            parts.append(f"countries: {', '.join(self.countries)}")
        if self.cities:
            parts.append(f"cities: {', '.join(self.cities)}")
        if self.industries:
            parts.append(f"industries: {', '.join(self.industries)}")
        
        return " AND ".join(parts) if parts else "no filters"


@dataclass
class FilterResult:
    """
    Result of applying filters to search results.
    
    Contains both filtered results and metadata for smart feedback.
    """
    # Filtered companies (pass all criteria)
    passed: List[Dict[str, Any]] = field(default_factory=list)
    
    # Original count before filtering
    original_count: int = 0
    
    # Count after filtering
    filtered_count: int = 0
    
    # Which filters were applied
    filters_applied: CompanyFilters = field(default_factory=CompanyFilters)
    
    # Per-filter rejection counts (for smart suggestions)
    # Key: filter name, Value: count of companies that FAILED this filter
    rejection_reasons: Dict[str, int] = field(default_factory=dict)
    
    # Companies that passed SOME but not ALL filters (for expansion suggestions)
    near_misses: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_filter_impact_summary(self) -> str:
        """
        Generate summary of which filters had the biggest impact.
        Useful for suggesting filter relaxation.
        """
        if not self.rejection_reasons:
            return "No filter rejections recorded."
        
        # Sort by rejection count (descending)
        sorted_reasons = sorted(
            self.rejection_reasons.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        parts = []
        for reason, count in sorted_reasons:
            if count > 0:
                parts.append(f"{reason}: {count} companies excluded")
        
        return "; ".join(parts) if parts else "All companies passed filters."
    
    def get_expansion_suggestions(self) -> List[str]:
        """
        Generate suggestions for relaxing filters to get more results.
        Called when filtered_count is low.
        """
        suggestions = []
        
        if self.filtered_count >= 10:
            return []  # Enough results, no suggestions needed
        
        if not self.rejection_reasons:
            return ["Try a broader search query to find more companies."]
        
        # Find the most restrictive filter
        sorted_reasons = sorted(
            self.rejection_reasons.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for reason, count in sorted_reasons:
            if count == 0:
                continue
                
            potential_total = self.filtered_count + count
            
            if "revenue" in reason.lower():
                suggestions.append(
                    f"Removing the revenue filter would include {count} more companies ({potential_total} total)."
                )
            elif "employee" in reason.lower():
                suggestions.append(
                    f"Expanding the employee range would include {count} more companies ({potential_total} total)."
                )
            elif "state" in reason.lower() or "location" in reason.lower():
                suggestions.append(
                    f"Expanding to additional states/regions would include {count} more companies ({potential_total} total)."
                )
            elif "industry" in reason.lower():
                suggestions.append(
                    f"Broadening the industry filter would include {count} more companies ({potential_total} total)."
                )
        
        # Cap at 3 suggestions
        return suggestions[:3]


def _check_revenue_filter(
    company: Dict[str, Any],
    filters: CompanyFilters
) -> Tuple[bool, Optional[str]]:
    """
    Check if company passes revenue filters.
    
    Returns:
        (passed, rejection_reason) - rejection_reason is None if passed
    """
    # Get revenue from apollo_enrichment if available, else top-level
    enrichment = company.get("apollo_enrichment", {})
    revenue = enrichment.get("annual_revenue") or company.get("annual_revenue")
    
    # If no revenue data and filter is set, we can't confirm - include by default
    # (Better UX: show companies with unknown revenue rather than exclude them)
    if revenue is None:
        # Only reject if we're being strict about revenue
        if filters.min_revenue is not None and filters.min_revenue > 10000000:
            # For large revenue thresholds, unknown = likely doesn't meet
            return False, "revenue_unknown"
        return True, None
    
    if filters.min_revenue is not None and revenue < filters.min_revenue:
        return False, "revenue_below_min"
    
    if filters.max_revenue is not None and revenue > filters.max_revenue:
        return False, "revenue_above_max"
    
    return True, None


def _check_employee_filter(
    company: Dict[str, Any],
    filters: CompanyFilters
) -> Tuple[bool, Optional[str]]:
    """Check if company passes employee count filters."""
    enrichment = company.get("apollo_enrichment", {})
    employees = enrichment.get("employee_count") or company.get("employee_count")
    
    if employees is None:
        return True, None  # Unknown employee count - include by default
    
    if filters.min_employees is not None and employees < filters.min_employees:
        return False, "employees_below_min"
    
    if filters.max_employees is not None and employees > filters.max_employees:
        return False, "employees_above_max"
    
    return True, None


def _check_geography_filter(
    company: Dict[str, Any],
    filters: CompanyFilters
) -> Tuple[bool, Optional[str]]:
    """Check if company passes geography filters."""
    enrichment = company.get("apollo_enrichment", {})
    
    # Get location data
    state = (enrichment.get("state") or company.get("state") or "").lower()
    country = (enrichment.get("country") or company.get("country") or "").lower()
    city = (enrichment.get("city") or company.get("city") or "").lower()
    
    # Check state filter
    if filters.states:
        states_lower = [s.lower() for s in filters.states]
        if state and state not in states_lower:
            return False, "state_mismatch"
        # If no state data, don't reject (could be international or missing data)
    
    # Check country filter
    if filters.countries:
        countries_lower = [c.lower() for c in filters.countries]
        if country and country not in countries_lower:
            return False, "country_mismatch"
    
    # Check city filter
    if filters.cities:
        cities_lower = [c.lower() for c in filters.cities]
        if city and city not in cities_lower:
            return False, "city_mismatch"
    
    return True, None


def _check_industry_filter(
    company: Dict[str, Any],
    filters: CompanyFilters
) -> Tuple[bool, Optional[str]]:
    """Check if company passes industry filter (substring match)."""
    if not filters.industries:
        return True, None
    
    enrichment = company.get("apollo_enrichment", {})
    industry = (enrichment.get("industry") or company.get("industry") or "").lower()
    keywords = enrichment.get("keywords", []) or company.get("keywords", [])
    keywords_lower = [k.lower() for k in keywords] if keywords else []
    
    # Check if any filter industry matches company industry or keywords
    industries_lower = [i.lower() for i in filters.industries]
    
    for filter_industry in industries_lower:
        # Check industry field
        if filter_industry in industry:
            return True, None
        # Check keywords
        for kw in keywords_lower:
            if filter_industry in kw:
                return True, None
    
    return False, "industry_mismatch"


def apply_filters(
    companies: List[Dict[str, Any]],
    filters: CompanyFilters
) -> FilterResult:
    """
    Apply filters to a list of enriched companies.
    
    Args:
        companies: List of company dicts with apollo_enrichment data
        filters: Filter criteria to apply
    
    Returns:
        FilterResult with passed companies, counts, and metadata for feedback
    """
    if filters.is_empty():
        return FilterResult(
            passed=companies,
            original_count=len(companies),
            filtered_count=len(companies),
            filters_applied=filters,
        )
    
    logger.info(f"[FILTERS] Applying filters to {len(companies)} companies: {filters.to_description()}")
    
    passed = []
    rejection_counts = {
        "revenue": 0,
        "employees": 0,
        "location": 0,
        "industry": 0,
    }
    
    for company in companies:
        company_name = company.get("company_name") or company.get("title") or "Unknown"
        
        # Check each filter category
        revenue_ok, revenue_reason = _check_revenue_filter(company, filters)
        if not revenue_ok:
            rejection_counts["revenue"] += 1
            logger.debug(f"[FILTERS] {company_name}: rejected by revenue ({revenue_reason})")
            continue
        
        employee_ok, employee_reason = _check_employee_filter(company, filters)
        if not employee_ok:
            rejection_counts["employees"] += 1
            logger.debug(f"[FILTERS] {company_name}: rejected by employees ({employee_reason})")
            continue
        
        geo_ok, geo_reason = _check_geography_filter(company, filters)
        if not geo_ok:
            rejection_counts["location"] += 1
            logger.debug(f"[FILTERS] {company_name}: rejected by location ({geo_reason})")
            continue
        
        industry_ok, industry_reason = _check_industry_filter(company, filters)
        if not industry_ok:
            rejection_counts["industry"] += 1
            logger.debug(f"[FILTERS] {company_name}: rejected by industry ({industry_reason})")
            continue
        
        # Passed all filters
        passed.append(company)
    
    result = FilterResult(
        passed=passed,
        original_count=len(companies),
        filtered_count=len(passed),
        filters_applied=filters,
        rejection_reasons=rejection_counts,
    )
    
    logger.info(
        f"[FILTERS] Result: {result.filtered_count}/{result.original_count} companies passed. "
        f"Impact: {result.get_filter_impact_summary()}"
    )
    
    return result


def parse_revenue_string(revenue_str: str) -> Optional[int]:
    """
    Parse revenue string like "$50M", "100 million", ">$100M" to integer.
    
    Returns revenue in USD (e.g., 50000000 for $50M).
    """
    if not revenue_str:
        return None
    
    import re
    
    # Clean string
    s = revenue_str.lower().replace(",", "").replace("$", "").strip()
    
    # Remove comparison operators
    s = s.lstrip("><=")
    
    # Extract number and multiplier
    match = re.match(r'(\d+(?:\.\d+)?)\s*(m|million|mm|b|billion|k|thousand)?', s)
    if not match:
        return None
    
    number = float(match.group(1))
    multiplier = match.group(2) or ""
    
    if multiplier in ["b", "billion"]:
        return int(number * 1_000_000_000)
    elif multiplier in ["m", "million", "mm"]:
        return int(number * 1_000_000)
    elif multiplier in ["k", "thousand"]:
        return int(number * 1_000)
    else:
        # Assume raw number - if > 1000, assume it's already in dollars
        if number > 1000:
            return int(number)
        # Small number - assume millions
        return int(number * 1_000_000)


def parse_employee_string(employee_str: str) -> Optional[int]:
    """
    Parse employee string like "500", ">200", "500+" to integer.
    """
    if not employee_str:
        return None
    
    import re
    
    # Clean string
    s = str(employee_str).lower().replace(",", "").strip()
    
    # Remove comparison operators and plus signs
    s = s.lstrip("><=").rstrip("+")
    
    # Extract number
    match = re.match(r'(\d+)', s)
    if not match:
        return None
    
    return int(match.group(1))
