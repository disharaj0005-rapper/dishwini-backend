from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)

try:
    response = supabase.rpc("add_password_hash_column").execute()
    print("Column added automatically.")
except Exception as e:
    print(f"Cannot add column via RPC. Please use the Supabase dashboard.")
