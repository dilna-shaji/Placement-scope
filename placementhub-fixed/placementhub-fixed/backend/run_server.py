"""Runner for the PlacementHub backend API server on port 5000."""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app import create_app
from waitress import serve

app = create_app()

if __name__ == "__main__":
    print("PlacementHub Backend listening on http://127.0.0.1:5000")
    serve(app, host="127.0.0.1", port=5000, threads=8)
