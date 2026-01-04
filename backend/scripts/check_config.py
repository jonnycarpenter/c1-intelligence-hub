
from app.config.settings import settings
import os

def mask(s):
    if not s: return "EMPTY"
    if len(s) < 8: return s[0] + "*" * (len(s)-1)
    return s[:4] + "*" * (len(s)-8) + s[-4:]

print(f"FMP API Key (from settings): {mask(settings.fmp_api_key)}")
print(f"FMP API Key (from env): {mask(os.getenv('FMP_API_KEY'))}")
print(f"GCP Project: {settings.gcp_project_id}")
print(f"Is GCP Configured: {settings.is_gcp_configured}")
