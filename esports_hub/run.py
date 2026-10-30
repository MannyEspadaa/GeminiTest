#!/usr/bin/env python3
"""
Esports Program Central Hub Entry Point
"""
import sys
import os
from app.server import run_server
from seed_data import seed

def main():
    port = 8080
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    
    # Ensure database is seeded with initial games and demo accounts
    seed()

    print(f"===========================================================")
    print(f" Esports Program Central Hub                               ")
    print(f" Server active at: http://localhost:{port}/               ")
    print(f" Quick Demo Accounts available:                            ")
    print(f"   • Admin:         admin / Password123!                  ")
    print(f"   • Valorant GM:   val_manager / Password123!            ")
    print(f"   • LoL GM:        lol_manager / Password123!            ")
    print(f"   • Player:        ace_duelist / Password123!            ")
    print(f"   • Community:     alex_fan / Password123!               ")
    print(f"   • Student User:  jordan_new / Password123!             ")
    print(f"===========================================================")

    httpd = run_server(port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    main()
