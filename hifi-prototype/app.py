"""NSP Learning Centre - Teacher Workload, KPI & Retention module (high-fidelity prototype).

Run:      python app.py          then open http://127.0.0.1:5000
Options:  --keep   keep the existing demo database instead of rebuilding it
          --lan    listen on the local network so a phone can scan the room QR code
"""
import sys

from nsp import create_app

if __name__ == "__main__":
    app = create_app(reseed="--keep" not in sys.argv)
    host = "0.0.0.0" if "--lan" in sys.argv else "127.0.0.1"
    print("\n  NSP Learning Centre prototype is running: http://127.0.0.1:5000\n")
    app.run(host=host, port=5000, debug=False)
