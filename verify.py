import os
from google.cloud import firestore

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service-account.json"
db = firestore.Client(project="gen-lang-client-0954110485", database="genz")

# Try to write
doc_ref = db.collection("test").document("check")
doc_ref.set({"status": "it works!"})

# Try to read it back immediately
result = doc_ref.get()
if result.exists:
    print(f"COMMUNICATION SUCCESS: {result.to_dict()}")
else:
    print("COMMUNICATION FAILED: Document not found.")