import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Pastikan file .env sudah diisi dengan SUPABASE_URL dan SUPABASE_KEY")

# Inisialisasi Client
supabase: Client = create_client(url, key)

print("✅ Database connection initialized.")