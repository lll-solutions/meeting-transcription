from google.cloud import firestore
import os

# Set project ID explicitly
project_id = "kurtmeeting-transcibe-dev"

try:
    db = firestore.Client(project=project_id)
    print(f"Connected to project: {project_id}")
    
    users_ref = db.collection("users")
    docs = list(users_ref.stream())
    
    print(f"Found {len(docs)} users:")
    for doc in docs:
        print(f" - ID: {doc.id}")
        data = doc.to_dict()
        print(f"   Email: {data.get('email')}")
        print(f"   Name: {data.get('name')}")
        print(f"   Has Password Hash: {'Yes' if data.get('password_hash') else 'No'}")

except Exception as e:
    print(f"Error: {e}")
