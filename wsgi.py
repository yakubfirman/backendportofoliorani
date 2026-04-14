import os
import sys

# Ensure project root is on sys.path (adjust if needed)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import the Flask `app` as `application` for WSGI servers (PythonAnywhere)
from app import app as application
