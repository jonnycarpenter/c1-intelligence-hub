
from app.config.settings import settings
from pathlib import Path
import os
from dotenv import load_dotenv

print(f"Base Dir: {settings.base_dir}")
print(f"Project Dir: {settings.base_dir.parent.parent}")
env_path = settings.base_dir.parent.parent / ".env"
print(f"Checking .env at: {env_path}")
print(f"Exists? {env_path.exists()}")

if env_path.exists():
    print("Content preview:")
    with open(env_path, "r") as f:
        print(f.read(100)) # First 100 chars
    
    print("\nForcing reload...")
    load_dotenv(env_path, override=True)
    print(f"GCP_PROJECT_ID after reload: {os.getenv('GCP_PROJECT_ID')}")
