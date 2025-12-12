"""
Storage module for meetings and output files.

Uses:
- Firestore for meeting metadata (status, timestamps, user)
- Cloud Storage (GCS) for output files (transcripts, PDFs)

Falls back to local storage if GCP services aren't configured.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

# Try to import GCP libraries
try:
    from google.cloud import firestore
    HAS_FIRESTORE = True
except ImportError:
    HAS_FIRESTORE = False
    print("⚠️ google-cloud-firestore not installed, using local storage")

try:
    from google.cloud import storage as gcs
    HAS_GCS = True
except ImportError:
    HAS_GCS = False
    print("⚠️ google-cloud-storage not installed, using local storage")


class MeetingStorage:
    """
    Handles persistence for meetings and output files.
    
    Supports both cloud (Firestore + GCS) and local storage modes.
    """
    
    def __init__(
        self, 
        bucket_name: str = None, 
        local_dir: str = "outputs",
        retention_days: int = None
    ):
        """
        Initialize storage.
        
        Args:
            bucket_name: GCS bucket name for files (None = local storage)
            local_dir: Local directory for fallback storage
            retention_days: Days to retain files (None = forever)
        """
        self.bucket_name = bucket_name
        self.local_dir = local_dir
        self.retention_days = retention_days or int(os.getenv("RETENTION_DAYS", "0"))
        
        # Initialize Firestore if available
        self.db = None
        if HAS_FIRESTORE and os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                self.db = firestore.Client()
                print(f"✅ Connected to Firestore")
            except Exception as e:
                print(f"⚠️ Could not connect to Firestore: {e}")
        
        # Initialize GCS if available
        self.gcs_client = None
        self.bucket = None
        if HAS_GCS and bucket_name:
            try:
                self.gcs_client = gcs.Client()
                self.bucket = self.gcs_client.bucket(bucket_name)
                print(f"✅ Connected to GCS bucket: {bucket_name}")
            except Exception as e:
                print(f"⚠️ Could not connect to GCS: {e}")
        
        # Ensure local directory exists as fallback
        os.makedirs(local_dir, exist_ok=True)
        
        # Report storage mode
        if self.db:
            print(f"📊 Meeting state: Firestore")
        else:
            print(f"📊 Meeting state: Local JSON files")
        
        if self.bucket:
            print(f"📁 File storage: GCS ({bucket_name})")
        else:
            print(f"📁 File storage: Local ({local_dir})")
        
        if self.retention_days > 0:
            print(f"🗓️ Retention: {self.retention_days} days")
        else:
            print(f"🗓️ Retention: Forever")
    
    # =========================================================================
    # MEETING METADATA (Firestore or local JSON)
    # =========================================================================
    
    def create_meeting(
        self, 
        meeting_id: str, 
        user: str,
        meeting_url: str,
        bot_name: str = "Meeting Assistant"
    ) -> Dict:
        """
        Create a new meeting record.
        
        Args:
            meeting_id: Unique meeting/bot ID from Recall
            user: User who created the meeting (email or ID)
            meeting_url: The meeting URL
            bot_name: Name of the bot
        
        Returns:
            dict: The created meeting record
        """
        now = datetime.utcnow()
        
        meeting = {
            "id": meeting_id,
            "user": user,
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "status": "joining",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "recording_id": None,
            "transcript_id": None,
            "outputs": {},
            "error": None
        }
        
        # Add expiration if retention is configured
        if self.retention_days > 0:
            meeting["expires_at"] = (now + timedelta(days=self.retention_days)).isoformat()
        
        if self.db:
            # Store in Firestore
            self.db.collection("meetings").document(meeting_id).set(meeting)
        else:
            # Store locally
            self._save_local_meeting(meeting_id, meeting)
        
        return meeting
    
    def get_meeting(self, meeting_id: str) -> Optional[Dict]:
        """Get a meeting by ID."""
        if self.db:
            doc = self.db.collection("meetings").document(meeting_id).get()
            return doc.to_dict() if doc.exists else None
        else:
            return self._load_local_meeting(meeting_id)
    
    def update_meeting(self, meeting_id: str, updates: Dict) -> Optional[Dict]:
        """
        Update a meeting record.
        
        Args:
            meeting_id: Meeting ID
            updates: Fields to update
        
        Returns:
            dict: Updated meeting record
        """
        updates["updated_at"] = datetime.utcnow().isoformat()
        
        if self.db:
            doc_ref = self.db.collection("meetings").document(meeting_id)
            doc_ref.update(updates)
            return doc_ref.get().to_dict()
        else:
            meeting = self._load_local_meeting(meeting_id)
            if meeting:
                meeting.update(updates)
                self._save_local_meeting(meeting_id, meeting)
            return meeting
    
    def list_meetings(self, user: str = None, status: str = None, limit: int = 100) -> List[Dict]:
        """
        List meetings with optional filters.

        Args:
            user: Filter by user (None = all users)
            status: Filter by status (None = all statuses)
            limit: Maximum number of results

        Returns:
            list: List of meeting records
        """
        if self.db:
            # Fetch all meetings sorted by created_at (no composite index needed)
            query = self.db.collection("meetings")
            query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
            query = query.limit(limit * 2)  # Fetch extra in case we filter

            # Filter in Python to avoid needing composite index
            results = []
            for doc in query.stream():
                data = doc.to_dict()
                if user and data.get("user") != user:
                    continue
                if status and data.get("status") != status:
                    continue
                results.append(data)
                if len(results) >= limit:
                    break

            return results
        else:
            # Local: load all and filter
            meetings = []
            meetings_dir = os.path.join(self.local_dir, "meetings")
            if os.path.exists(meetings_dir):
                for filename in os.listdir(meetings_dir):
                    if filename.endswith(".json"):
                        meeting = self._load_local_meeting(filename[:-5])
                        if meeting:
                            if user and meeting.get("user") != user:
                                continue
                            if status and meeting.get("status") != status:
                                continue
                            meetings.append(meeting)
            
            # Sort by created_at descending
            meetings.sort(key=lambda m: m.get("created_at", ""), reverse=True)
            return meetings[:limit]
    
    def delete_meeting(self, meeting_id: str) -> bool:
        """Delete a meeting and its files."""
        if self.db:
            self.db.collection("meetings").document(meeting_id).delete()
        else:
            path = os.path.join(self.local_dir, "meetings", f"{meeting_id}.json")
            if os.path.exists(path):
                os.remove(path)
        
        # Also delete output files
        self.delete_outputs(meeting_id)
        return True
    
    def _save_local_meeting(self, meeting_id: str, meeting: Dict):
        """Save meeting to local JSON file."""
        meetings_dir = os.path.join(self.local_dir, "meetings")
        os.makedirs(meetings_dir, exist_ok=True)
        path = os.path.join(meetings_dir, f"{meeting_id}.json")
        with open(path, 'w') as f:
            json.dump(meeting, f, indent=2)
    
    def _load_local_meeting(self, meeting_id: str) -> Optional[Dict]:
        """Load meeting from local JSON file."""
        path = os.path.join(self.local_dir, "meetings", f"{meeting_id}.json")
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return None
    
    # =========================================================================
    # OUTPUT FILES (GCS or local)
    # =========================================================================
    
    def get_output_path(self, meeting_id: str, filename: str) -> str:
        """
        Get the path/key for an output file.
        
        Args:
            meeting_id: Meeting ID
            filename: File name (e.g., "transcript.json")
        
        Returns:
            str: Full path (local) or GCS key
        """
        # Use first 8 chars of meeting ID as folder name
        folder = meeting_id[:8] if len(meeting_id) > 8 else meeting_id
        
        if self.bucket:
            return f"meetings/{folder}/{filename}"
        else:
            return os.path.join(self.local_dir, folder, filename)
    
    def save_file(self, meeting_id: str, filename: str, content: str | bytes) -> str:
        """
        Save a file to storage.
        
        Args:
            meeting_id: Meeting ID
            filename: File name
            content: File content (string or bytes)
        
        Returns:
            str: Path or URL to the saved file
        """
        path = self.get_output_path(meeting_id, filename)
        
        if self.bucket:
            blob = self.bucket.blob(path)
            
            # Set content type
            content_type = "application/octet-stream"
            if filename.endswith(".json"):
                content_type = "application/json"
            elif filename.endswith(".md"):
                content_type = "text/markdown"
            elif filename.endswith(".pdf"):
                content_type = "application/pdf"
            elif filename.endswith(".txt"):
                content_type = "text/plain"
            
            if isinstance(content, str):
                blob.upload_from_string(content, content_type=content_type)
            else:
                blob.upload_from_string(content, content_type=content_type)
            
            # Return public URL or signed URL
            return f"gs://{self.bucket_name}/{path}"
        else:
            # Local storage
            os.makedirs(os.path.dirname(path), exist_ok=True)
            mode = 'w' if isinstance(content, str) else 'wb'
            with open(path, mode) as f:
                f.write(content)
            return path
    
    def save_file_from_path(self, meeting_id: str, filename: str, source_path: str) -> str:
        """
        Save a file from a local path to storage.
        
        Args:
            meeting_id: Meeting ID
            filename: Destination file name
            source_path: Path to source file
        
        Returns:
            str: Path or URL to the saved file
        """
        path = self.get_output_path(meeting_id, filename)
        
        if self.bucket:
            blob = self.bucket.blob(path)
            blob.upload_from_filename(source_path)
            return f"gs://{self.bucket_name}/{path}"
        else:
            # For local, just return the source path if it's already in the right place
            if os.path.abspath(source_path) == os.path.abspath(path):
                return path
            
            # Otherwise, copy
            os.makedirs(os.path.dirname(path), exist_ok=True)
            import shutil
            shutil.copy2(source_path, path)
            return path
    
    def get_file(self, meeting_id: str, filename: str) -> Optional[bytes]:
        """
        Get file content from storage.
        
        Args:
            meeting_id: Meeting ID
            filename: File name
        
        Returns:
            bytes: File content or None if not found
        """
        path = self.get_output_path(meeting_id, filename)
        
        if self.bucket:
            blob = self.bucket.blob(path)
            if blob.exists():
                return blob.download_as_bytes()
            return None
        else:
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    return f.read()
            return None
    
    def get_download_url(self, meeting_id: str, filename: str, expires_minutes: int = 60) -> Optional[str]:
        """
        Get a download URL for a file.

        Args:
            meeting_id: Meeting ID
            filename: File name
            expires_minutes: URL expiration time (for signed URLs)

        Returns:
            str: Download URL or local path
        """
        path = self.get_output_path(meeting_id, filename)

        if self.bucket:
            blob = self.bucket.blob(path)
            if blob.exists():
                # Generate signed URL using IAM signBlob (works with default Cloud Run credentials)
                from datetime import timedelta
                from google.auth import iam
                from google.auth.transport import requests as google_requests
                import google.auth

                try:
                    credentials, project = google.auth.default()

                    # Get service account email
                    project_number = os.getenv('PROJECT_NUMBER')
                    if project_number:
                        service_account_email = f"{project_number}-compute@developer.gserviceaccount.com"
                    else:
                        service_account_email = f"{project}@appspot.gserviceaccount.com"

                    # Use IAM signer for Cloud Run environment
                    auth_request = google_requests.Request()
                    signing_credentials = iam.Signer(
                        request=auth_request,
                        credentials=credentials,
                        service_account_email=service_account_email
                    )

                    # Use v4 signing which supports IAM
                    url = blob.generate_signed_url(
                        version="v4",
                        expiration=timedelta(minutes=expires_minutes),
                        method='GET',
                        service_account_email=service_account_email,
                        access_token=credentials.token if hasattr(credentials, 'token') else None,
                        credentials=signing_credentials
                    )
                    return url
                except Exception as e:
                    print(f"⚠️ Failed to generate signed URL: {e}")
                    import traceback
                    traceback.print_exc()
                    # Return None so endpoint can fall back
                    return None
            return None
        else:
            if os.path.exists(path):
                return path
            return None
    
    def list_outputs(self, meeting_id: str) -> List[str]:
        """List all output files for a meeting."""
        folder = meeting_id[:8] if len(meeting_id) > 8 else meeting_id
        
        if self.bucket:
            prefix = f"meetings/{folder}/"
            blobs = self.bucket.list_blobs(prefix=prefix)
            return [blob.name.replace(prefix, '') for blob in blobs]
        else:
            path = os.path.join(self.local_dir, folder)
            if os.path.exists(path):
                return os.listdir(path)
            return []
    
    def delete_outputs(self, meeting_id: str) -> bool:
        """Delete all output files for a meeting."""
        folder = meeting_id[:8] if len(meeting_id) > 8 else meeting_id
        
        if self.bucket:
            prefix = f"meetings/{folder}/"
            blobs = self.bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                blob.delete()
        else:
            import shutil
            path = os.path.join(self.local_dir, folder)
            if os.path.exists(path):
                shutil.rmtree(path)
        
        return True
    
    # =========================================================================
    # CLEANUP / RETENTION
    # =========================================================================
    
    def cleanup_expired(self) -> int:
        """
        Delete expired meetings and files.
        
        Returns:
            int: Number of meetings deleted
        """
        if self.retention_days <= 0:
            return 0
        
        now = datetime.utcnow()
        deleted = 0
        
        if self.db:
            # Query expired meetings
            expired_query = (
                self.db.collection("meetings")
                .where("expires_at", "<", now.isoformat())
                .limit(100)
            )
            
            for doc in expired_query.stream():
                meeting_id = doc.id
                self.delete_meeting(meeting_id)
                deleted += 1
                print(f"🗑️ Deleted expired meeting: {meeting_id}")
        else:
            # Check local meetings
            for meeting in self.list_meetings():
                expires_at = meeting.get("expires_at")
                if expires_at and datetime.fromisoformat(expires_at) < now:
                    self.delete_meeting(meeting["id"])
                    deleted += 1
                    print(f"🗑️ Deleted expired meeting: {meeting['id']}")
        
        return deleted

