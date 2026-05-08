import sys
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

# CRITICAL: load_dotenv MUST be called before importing the Flask app.
# If called after, os.environ will be empty when create_app() reads config.
from dotenv import load_dotenv
load_dotenv(os.path.join(APP_DIR, '.env'))

from app import create_app
application = create_app()

# DO NOT call application.run() — Passenger is not the Flask dev server.
