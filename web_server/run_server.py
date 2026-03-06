#!/usr/bin/env python3
"""
Run the Flask web server for cube visualization API.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import create_app

if __name__ == '__main__':
    app = create_app()
    print("Starting Flask server on http://127.0.0.1:5000")
    print("API endpoints available at http://127.0.0.1:5000/api")
    app.run(host='127.0.0.1', port=5000, debug=True)


