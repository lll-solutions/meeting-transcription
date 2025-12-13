"""
Transcript processing service.

Handles business logic for processing meeting transcripts:
- Processing Recall API transcripts
- Processing user-uploaded transcripts
- Running the unified AI summarization pipeline
"""

import json
import os
import tempfile
from datetime import UTC, datetime

from src.api.recall import download_transcript
from src.api.storage import MeetingStorage
from src.pipeline import (
    combine_transcript_words,
    create_educational_chunks,
    create_study_guide,
    markdown_to_pdf,
    summarize_educational_content,
)


class TranscriptService:
    """Service for processing meeting transcripts through the AI pipeline."""

    def __init__(self, storage: MeetingStorage, llm_provider: str | None = None) -> None:
        """
        Initialize the transcript service.

        Args:
            storage: Meeting storage instance for persistence
            llm_provider: LLM provider to use (defaults to 'vertex_ai')
        """
        self.storage = storage
        self.llm_provider = llm_provider or "vertex_ai"

    def process_recall_transcript(
        self, transcript_id: str, recording_id: str | None = None
    ) -> None:
        """
        Process a transcript downloaded from Recall API.

        Args:
            transcript_id: Recall API transcript ID
            recording_id: Optional recording ID for fallback meeting lookup

        Raises:
            RuntimeError: If transcript download fails or pipeline fails
        """
        # Find meeting record by transcript_id
        meeting_id, meeting_record = self._find_meeting_by_transcript(
            transcript_id, recording_id
        )

        try:
            print(f"\n🔄 Starting pipeline for transcript {transcript_id}")
            self.storage.update_meeting(meeting_id, {"status": "processing"})

            with tempfile.TemporaryDirectory() as temp_dir:
                # Step 1: Download transcript from Recall API
                print("📥 Step 1: Downloading transcript...")
                transcript_file = os.path.join(temp_dir, "transcript_raw.json")
                result = download_transcript(transcript_id, transcript_file)

                if not result:
                    raise RuntimeError("Failed to download transcript from Recall API")

                # Run unified pipeline (steps 2-7)
                self._run_pipeline(
                    meeting_id=meeting_id,
                    transcript_file=transcript_file,
                    temp_dir=temp_dir,
                    meeting_record=meeting_record,
                    upload_intermediate=False,
                )

        except Exception as e:
            print(f"❌ Pipeline error: {e}")
            import traceback

            traceback.print_exc()

            self.storage.update_meeting(
                meeting_id, {"status": "failed", "error": str(e)}
            )
            raise

    def process_uploaded_transcript(
        self, meeting_id: str, transcript_data: list, title: str | None = None
    ) -> dict:
        """
        Process a user-uploaded transcript.

        Args:
            meeting_id: Meeting ID for this upload
            transcript_data: Transcript JSON data (list of segments)
            title: Optional title for the transcript

        Returns:
            dict: Processing results including output paths

        Raises:
            RuntimeError: If pipeline fails
        """
        print(f"\n🔄 Starting pipeline for uploaded transcript {meeting_id}")
        self.storage.update_meeting(meeting_id, {"status": "processing"})

        with tempfile.TemporaryDirectory() as temp_dir:
            # Step 1: Save uploaded transcript
            print("📥 Step 1: Saving uploaded transcript...")
            transcript_file = os.path.join(temp_dir, "transcript_raw.json")
            with open(transcript_file, "w") as f:
                json.dump(transcript_data, f, indent=2)

            # Run unified pipeline (steps 2-7)
            outputs = self._run_pipeline(
                meeting_id=meeting_id,
                transcript_file=transcript_file,
                temp_dir=temp_dir,
                meeting_record=None,
                upload_intermediate=True,
            )

            # Update with title if provided
            if title:
                self.storage.update_meeting(meeting_id, {"title": title})

            return {"outputs": outputs}

    def _find_meeting_by_transcript(
        self, transcript_id: str, recording_id: str | None
    ) -> tuple[str, dict | None]:
        """
        Find meeting record by transcript ID.

        Args:
            transcript_id: Recall API transcript ID
            recording_id: Optional recording ID for fallback

        Returns:
            tuple: (meeting_id, meeting_record or None)
        """
        meetings_list = self.storage.list_meetings()
        for meeting in meetings_list:
            if meeting.get("transcript_id") == transcript_id:
                return meeting["id"], meeting

        # Fallback: use recording_id or transcript_id as meeting_id
        meeting_id = recording_id or transcript_id
        return meeting_id, None

    def _run_pipeline(
        self,
        meeting_id: str,
        transcript_file: str,
        temp_dir: str,
        meeting_record: dict | None = None,
        upload_intermediate: bool = False,
    ) -> dict:
        """
        Run the unified transcript processing pipeline.

        Steps:
        2. Combine words into sentences
        3. Create educational chunks
        4. LLM summarization
        5. Create study guide (Markdown)
        6. Convert to PDF
        7. Upload to storage

        Args:
            meeting_id: Meeting ID
            transcript_file: Path to raw transcript JSON
            temp_dir: Temporary directory for intermediate files
            meeting_record: Optional meeting metadata to patch into summary
            upload_intermediate: Whether to upload intermediate files

        Returns:
            dict: Output file paths by name
        """
        # Step 2: Combine words into sentences
        print("📝 Step 2: Combining words into sentences...")
        combined_file = os.path.join(temp_dir, "transcript_combined.json")
        combine_transcript_words.combine_transcript_words(
            transcript_file, combined_file
        )

        # Step 3: Create educational chunks
        print("📦 Step 3: Creating educational chunks...")
        chunks_file = os.path.join(temp_dir, "transcript_chunks.json")
        create_educational_chunks.create_educational_content_chunks(
            combined_file, chunks_file, chunk_minutes=10
        )

        # Step 4: LLM summarization
        print("🤖 Step 4: Generating AI summary...")
        summary_file = os.path.join(temp_dir, "summary.json")
        summarize_educational_content.summarize_educational_content(
            chunks_file, summary_file, provider=self.llm_provider
        )

        # Step 4.5: Patch summary with meeting metadata (if available)
        if meeting_record:
            self._patch_summary_metadata(summary_file, meeting_record)

        # Step 5: Create study guide
        print("📚 Step 5: Creating study guide...")
        study_guide_file = os.path.join(temp_dir, "study_guide.md")
        create_study_guide.create_markdown_study_guide(summary_file, study_guide_file)

        # Step 6: Convert to PDF
        print("📄 Step 6: Generating PDF...")
        pdf_file: str | None = os.path.join(temp_dir, "study_guide.pdf")
        try:
            markdown_to_pdf.convert_markdown_to_pdf(study_guide_file, pdf_file)
        except Exception as e:
            print(f"⚠️ PDF generation failed (non-fatal): {e}")
            pdf_file = None

        # Step 7: Upload files to storage
        print("☁️ Step 7: Uploading to storage...")
        outputs = self._upload_outputs(
            meeting_id,
            transcript_file,
            combined_file,
            chunks_file,
            summary_file,
            study_guide_file,
            pdf_file,
            upload_intermediate,
        )

        # Update meeting with completed status
        self.storage.update_meeting(
            meeting_id,
            {
                "status": "completed",
                "outputs": outputs,
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )

        print("\n✅ Pipeline complete!")
        print(f"   Meeting ID: {meeting_id}")
        for name, path in outputs.items():
            print(f"   - {name}: {path}")

        return outputs

    def _patch_summary_metadata(
        self, summary_file: str, meeting_record: dict
    ) -> None:
        """
        Patch summary JSON with meeting metadata.

        Args:
            summary_file: Path to summary JSON file
            meeting_record: Meeting record with metadata
        """
        with open(summary_file) as f:
            summary_data = json.load(f)

        if "metadata" not in summary_data:
            summary_data["metadata"] = {}

        # Add meeting date
        if meeting_record.get("created_at"):
            summary_data["metadata"]["meeting_date"] = meeting_record["created_at"][:10]

        # Add instructor name
        if meeting_record.get("instructor_name"):
            summary_data["metadata"]["instructor"] = meeting_record["instructor_name"]

        with open(summary_file, "w") as f:
            json.dump(summary_data, f, indent=2)

    def _upload_outputs(
        self,
        meeting_id: str,
        transcript_file: str,
        combined_file: str,
        chunks_file: str,
        summary_file: str,
        study_guide_file: str,
        pdf_file: str | None,
        upload_intermediate: bool,
    ) -> dict:
        """
        Upload output files to storage.

        Args:
            meeting_id: Meeting ID
            transcript_file: Raw transcript file path
            combined_file: Combined transcript file path
            chunks_file: Chunks file path
            summary_file: Summary file path
            study_guide_file: Study guide markdown file path
            pdf_file: PDF file path (or None if generation failed)
            upload_intermediate: Whether to upload intermediate files

        Returns:
            dict: Output file paths by name
        """
        outputs = {}

        # Always upload final outputs
        files_to_upload = [
            ("transcript", transcript_file),
            ("summary", summary_file),
            ("study_guide_md", study_guide_file),
        ]

        # Optionally upload intermediate files
        if upload_intermediate:
            files_to_upload.extend(
                [
                    ("transcript_combined", combined_file),
                    ("transcript_chunks", chunks_file),
                ]
            )

        # Add PDF if it exists
        if pdf_file and os.path.exists(pdf_file):
            files_to_upload.append(("study_guide_pdf", pdf_file))

        # Upload all files
        for name, local_path in files_to_upload:
            if os.path.exists(local_path):
                filename = os.path.basename(local_path)
                stored_path = self.storage.save_file_from_path(
                    meeting_id, filename, local_path
                )
                outputs[name] = stored_path
                print(f"   ✅ Uploaded: {filename}")

        return outputs
