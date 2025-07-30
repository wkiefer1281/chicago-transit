# oauth.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_api_keys():
    # Retrieve API keys from .env file
    cta_train_api_key = os.getenv('CTA_TRAIN_API_KEY')
    cta_bus_api_key = os.getenv('CTA_BUS_API_KEY')
    
    if not cta_train_api_key or not cta_bus_api_key:
        raise ValueError("Missing CTA API keys in .env file.")
    
    return cta_train_api_key, cta_bus_api_key
