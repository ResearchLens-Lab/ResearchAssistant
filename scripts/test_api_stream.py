import sys, os
sys.path.insert(0, os.path.abspath("."))
import json
import urllib.request
from backend.app.core.security import create_access_token

user_id = "4526f09d-ae50-47d8-8a73-ffe73e3dc0dd"
token = create_access_token(user_id)

url = "http://127.0.0.1:8000/api/v1/chat/stream"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}
payload = {
    "question": "Present the relevant findings in a concise table with citations",
    "paper_ids": ["fb6729c8-49e1-4dd2-b22f-da03b4d198a4", "5d009428-7a4c-4225-9878-ae252140b1c3"],
    "answer_mode": "EVIDENCE_FIRST",
}

req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

print("Sending chat stream request...")
events = []
with urllib.request.urlopen(req, timeout=30) as resp:
    print("HTTP Status:", resp.status)
    for line in resp:
        decoded = line.decode("utf-8").strip()
        if decoded.startswith("event:"):
            events.append(decoded)
            print("Received event:", decoded)
        elif decoded.startswith("data:"):
            try:
                data_obj = json.loads(decoded[5:].strip())
                event_type = data_obj.get("type")
                if event_type == "completed":
                    print("Stream completed successfully!")
                    comp_data = data_obj.get("data", {})
                    print("Answer preview:\n", comp_data.get("answer", "")[:350])
                    print("Sources count:", len(comp_data.get("sources", [])))
                    if comp_data.get("sources"):
                        print("First source:", comp_data["sources"][0].get("citation_label"))
            except Exception:
                pass

print("Total events received:", len(events))
