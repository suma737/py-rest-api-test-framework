import os
import json
import requests
import argparse

def main():
    parser = argparse.ArgumentParser(description="Setup user")
    parser.add_argument('--name', default='Temp', help='User name')
    args = parser.parse_args()
    base_url = os.getenv('API_BASE_URL')
    resp = requests.post(f"{base_url}/users", json={"name": args.name})
    data = resp.json()
    # Return both id and name
    print(json.dumps({
        "pre_user_id": data.get("id"),
        "pre_user_name": data.get("name")
    }))

if __name__ == "__main__":
    main()
