"""Import the public AICTE-based Indian college directory into MySQL.

This imports names and basic directory information only. It deliberately does
not invent student domains, Principal emails, Mess Head emails, FSSAI emails,
or mess halls. Those fields must be verified before a college is enabled for
complaints.
"""

import json
from urllib.parse import quote
from urllib.request import Request, urlopen

import database as db


BASE_URL = "https://indian-colleges-list.vercel.app/api/institutions"


def get_json(url):
    request = Request(url, headers={"User-Agent": "TrayTrack college directory sync"})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def main():
    db.init_db()
    states = get_json(f"{BASE_URL}/states")["states"]
    rows = []
    for state in states:
        state_name = state["name"]
        state_slug = state["slug"]
        payload = get_json(f"{BASE_URL}/states/{quote(state_slug)}")
        for item in payload.get("data", []):
            source_id = item.get("aicte_id") or item.get("other_id")
            name = (item.get("institute_name") or "").strip()
            if not source_id or not name:
                continue
            rows.append({
                "source_id": source_id,
                "name": name,
                "state": state_name,
                "district": item.get("district"),
                "address": item.get("address"),
                "institution_type": item.get("institution_type"),
                "source_name": "AICTE",
            })
        print(f"Loaded {state_name}: {len(rows)} total records")

    imported = db.upsert_college_directory(rows)
    print(f"Synced {imported} records into college_directory.")


if __name__ == "__main__":
    main()
