
from app.config.settings import settings
import os
from dotenv import load_dotenv

# Force reload from .env
load_dotenv(override=True)

print(f"SEC Key from Settings: '{settings.sec_api_key}'")
print(f"SEC Key from Env: '{os.getenv('SEC_API_KEY')}'")
print(f"SEC Key from Env (lowercase): '{os.getenv('sec_api_key')}'")
