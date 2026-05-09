#!/home/customer/dochat/venv/bin/python3
import sys, os

DOCHAT_DIR = os.path.expanduser('~/dochat')
sys.path.insert(0, DOCHAT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(DOCHAT_DIR, '.env'))

from app import create_app
from wsgiref.handlers import CGIHandler

CGIHandler().run(create_app())
