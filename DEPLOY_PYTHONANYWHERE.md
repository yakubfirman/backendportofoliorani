# Deploy to PythonAnywhere — quick guide

This document explains the minimal steps to deploy the backend on PythonAnywhere.

1. Push your repo to GitHub (or make it accessible).

2. On PythonAnywhere:
   - Open a Bash console.
   - Clone your repo:
     git clone https://github.com/<your-github-username>/<repo>.git
   - Move into the project:
     cd <repo>/backend

3. Create and activate a virtualenv (example with Python 3.10):
   python3.10 -m venv ~/venv/<name>
   source ~/venv/<name>/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt

   (Or use `mkvirtualenv --python=/usr/bin/python3.10 <name>` if you prefer.)

4. Initialize the database and seed data (runs `init_db()`):
   python3 app.py

5. Configure the Web app (Web tab):
   - Source code directory: `/home/<yourusername>/<repo>`
   - Virtualenv: `/home/<yourusername>/venv/<name>`
   - Static files mapping:
       URL: `/api/uploads/`  →  Directory: `/home/<yourusername>/<repo>/backend/uploads/`
   - WSGI configuration:
       Edit the WSGI file and add the following (adjust path):

       import sys, os
       path = '/home/<yourusername>/<repo>'
       if path not in sys.path:
           sys.path.insert(0, path)
       from backend.wsgi import application

   - Environment variables (Web tab → Environment variables):
       - `JWT_SECRET_KEY` → a random secret
       - `FRONTEND_URL` → your frontend domain (e.g., `https://your-frontend.com`)
       - (optional) `DATABASE_URL` if using an external DB

6. Reload the web app.

7. Update your frontend `NEXT_PUBLIC_API_URL` to `https://<yourusername>.pythonanywhere.com` and redeploy frontend if applicable.

Notes:
- The app already configures `UPLOAD_FOLDER` relative to the repository backend folder and will create the folder automatically.
- Use the static files mapping above for efficient serving of uploaded files.
- PythonAnywhere uses a WSGI server; you don't need `gunicorn`.
- Free PythonAnywhere accounts have storage limits—monitor uploaded file sizes.

Additional helpful files included in this repository:

- `.env.example`: example environment variables for the backend. Copy to `.env` and set values.
- `setup_pythonanywhere.sh`: a small script you can run in the PythonAnywhere Bash console to create a virtualenv, install requirements, create `uploads/`, and initialize the database.
- `.gitignore`: ignores `uploads/`, local sqlite DB and virtualenv directories so you don't accidentally commit uploads.

WSGI file example (exact content to place in the PythonAnywhere WSGI file):

```python
import sys
import os

# Replace with your home/project path on PythonAnywhere
path = '/home/<yourusername>/<repo>'
if path not in sys.path:
        sys.path.insert(0, path)

# If your code is in the backend/ subfolder, ensure it's importable
from backend.wsgi import application
```

Serving uploaded files:
- In the PythonAnywhere Web tab, set a 'Static files' mapping:
    - URL: `/api/uploads/`  →  Directory: `/home/<yourusername>/<repo>/backend/uploads/`

Security reminders:
- Set `JWT_SECRET_KEY` to a long random value using a secure generator and do NOT commit it to Git.
- Set `FRONTEND_URL` to your production frontend domain to whitelist it for CORS.

