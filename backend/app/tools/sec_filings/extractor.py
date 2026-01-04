
from typing import Dict, Optional
from app.config.settings import settings

class SectionExtractor:
    SECTION_NAMES = {
        "1": "business",
        "1A": "risk_factors",
        "7": "mda",
        "7A": "market_risk_disclosures",
    }
    
    def __init__(self, sec_client=None):
        self.client = sec_client
    
    def extract_all_sections(self, filing_url: str, sections: list = None) -> Dict[str, str]:
        if not self.client:
             raise ValueError("SEC Client required")
        
        sections = sections or settings.sec_extract_sections
        extracted = {}
        
        for section in sections:
            content = self.client.extract_section(
                filing_url=filing_url,
                section=section
            )
            if content:
                section_name = self.SECTION_NAMES.get(section, f"section_{section}")
                extracted[section_name] = content
        return extracted
