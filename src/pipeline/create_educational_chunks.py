#!/usr/bin/env python3
"""
Create educational content chunks optimized for LLM summarization.
Designed for AI/tech class recordings with instructor and students.
"""
import json
import sys
from typing import List, Dict, Any
from datetime import datetime

def format_timestamp(seconds: float) -> str:
    """Convert seconds to MM:SS format."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def identify_instructor(transcript: List[Dict]) -> str:
    """
    Identify the instructor (person who speaks the most).

    Args:
        transcript: Combined transcript

    Returns:
        Name of the instructor
    """
    speaker_words = {}
    for segment in transcript:
        speaker = segment['participant']['name']
        words = segment['word_count']
        speaker_words[speaker] = speaker_words.get(speaker, 0) + words

    # Instructor is likely the person with most words
    instructor = max(speaker_words.items(), key=lambda x: x[1])[0]
    return instructor

def create_educational_chunks(
    transcript: List[Dict],
    instructor: str,
    chunk_minutes: int = 10
) -> List[Dict]:
    """
    Create time-based chunks with educational context.

    Args:
        transcript: Combined transcript
        instructor: Name of the instructor
        chunk_minutes: Minutes per chunk

    Returns:
        List of educational chunks
    """
    if not transcript:
        return []

    chunks = []
    chunk_seconds = chunk_minutes * 60

    # Get meeting boundaries
    meeting_start = transcript[0]['start_timestamp']['relative']
    meeting_end = transcript[-1]['end_timestamp']['relative']

    current_time = meeting_start
    chunk_num = 1

    while current_time < meeting_end:
        chunk_end = current_time + chunk_seconds

        # Collect segments in this time window
        chunk_segments = []
        for segment in transcript:
            seg_start = segment['start_timestamp']['relative']
            seg_end = segment['end_timestamp']['relative']

            # Include if overlaps with chunk window
            if seg_start < chunk_end and seg_end > current_time:
                speaker = segment['participant']['name']
                is_instructor = speaker == instructor

                chunk_segments.append({
                    'speaker': speaker,
                    'is_instructor': is_instructor,
                    'text': segment['text'],
                    'timestamp': format_timestamp(seg_start),
                    'word_count': segment['word_count'],
                    'start_seconds': seg_start,
                    'end_seconds': seg_end
                })

        if chunk_segments:
            # Calculate statistics
            total_words = sum(seg['word_count'] for seg in chunk_segments)
            speakers = list(set(seg['speaker'] for seg in chunk_segments))
            student_speakers = [s for s in speakers if s != instructor]

            # Count instructor vs student words
            instructor_words = sum(
                seg['word_count'] for seg in chunk_segments if seg['is_instructor']
            )
            student_words = total_words - instructor_words

            # Detect potential Q&A (multiple speakers, students ask questions)
            has_student_interaction = len(student_speakers) > 0

            chunks.append({
                'chunk_number': chunk_num,
                'time_range': f"{format_timestamp(current_time)} - {format_timestamp(min(chunk_end, meeting_end))}",
                'start_seconds': current_time,
                'end_seconds': min(chunk_end, meeting_end),
                'duration_minutes': (min(chunk_end, meeting_end) - current_time) / 60,
                'total_words': total_words,
                'instructor_words': instructor_words,
                'student_words': student_words,
                'speakers': speakers,
                'student_speakers': student_speakers,
                'has_student_interaction': has_student_interaction,
                'segments': chunk_segments
            })
            chunk_num += 1

        current_time = chunk_end

    return chunks

def format_chunk_for_llm(chunk: Dict, instructor: str) -> str:
    """
    Format a chunk as a readable transcript for LLM processing.

    Args:
        chunk: Chunk dictionary
        instructor: Instructor name

    Returns:
        Formatted text for LLM
    """
    lines = [
        f"=== TIME RANGE: {chunk['time_range']} ===",
        f"Duration: {chunk['duration_minutes']:.1f} minutes",
        f"Speakers: {', '.join(chunk['speakers'])}",
        f"Student Interaction: {'Yes' if chunk['has_student_interaction'] else 'No'}",
        "",
        "TRANSCRIPT:",
        ""
    ]

    for seg in chunk['segments']:
        role = "INSTRUCTOR" if seg['is_instructor'] else "STUDENT"
        lines.append(f"[{seg['timestamp']}] {role} ({seg['speaker']}): {seg['text']}")
        lines.append("")

    return "\n".join(lines)

def create_educational_content_chunks(
    input_file: str,
    output_file: str,
    chunk_minutes: int = 10
):
    """
    Main function to create educational chunks from combined transcript.

    Args:
        input_file: Combined transcript JSON
        output_file: Output educational chunks JSON
        chunk_minutes: Minutes per chunk (default 10)
    """
    # Read combined transcript
    with open(input_file, 'r') as f:
        transcript = json.load(f)

    if not transcript:
        print("Error: Empty transcript")
        return

    # Identify instructor
    instructor = identify_instructor(transcript)
    print(f"Identified instructor: {instructor}")

    # Get all participants
    participants = {}
    for segment in transcript:
        name = segment['participant']['name']
        if name not in participants:
            participants[name] = {
                'name': name,
                'is_instructor': name == instructor,
                'total_words': 0,
                'speaking_turns': 0
            }
        participants[name]['total_words'] += segment['word_count']
        participants[name]['speaking_turns'] += 1

    # Create chunks
    chunks = create_educational_chunks(transcript, instructor, chunk_minutes)

    # Calculate metadata
    total_duration = transcript[-1]['end_timestamp']['relative'] / 60

    # Handle null absolute timestamp
    meeting_date = 'Unknown'
    if transcript[0]['start_timestamp']['absolute']:
        meeting_date = transcript[0]['start_timestamp']['absolute'][:10]

    output = {
        'metadata': {
            'meeting_date': meeting_date,
            'meeting_duration_minutes': int(total_duration),
            'chunk_duration_minutes': chunk_minutes,
            'total_chunks': len(chunks),
            'total_words': sum(chunk['total_words'] for chunk in chunks),
            'instructor': instructor,
            'total_participants': len(participants),
            'participants': list(participants.values())
        },
        'chunks': chunks
    }

    # Write output
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    # Print summary
    print(f"\n=== Educational Chunks Created ===")
    print(f"Meeting duration: {int(total_duration)} minutes")
    print(f"Total chunks: {len(chunks)} ({chunk_minutes}-minute chunks)")
    print(f"Total words: {output['metadata']['total_words']:,}")
    print(f"Instructor: {instructor}")
    print(f"Students: {len(participants) - 1}")
    print(f"\nChunk breakdown:")
    for i, chunk in enumerate(chunks[:5]):
        interaction = "✓" if chunk['has_student_interaction'] else "✗"
        print(f"  Chunk {chunk['chunk_number']}: {chunk['time_range']} - "
              f"{chunk['total_words']} words - "
              f"Students: {interaction}")
    if len(chunks) > 5:
        print(f"  ... {len(chunks) - 5} more chunks")

    print(f"\nOutput written to: {output_file}")

    # Also create a sample LLM-formatted chunk
    sample_file = output_file.replace('.json', '_sample.txt')
    with open(sample_file, 'w') as f:
        f.write(format_chunk_for_llm(chunks[0], instructor))
    print(f"Sample LLM format written to: {sample_file}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python create_educational_chunks.py <input_file> <output_file> [chunk_minutes]")
        print("Example: python create_educational_chunks.py transcript_combined.json transcript_educational.json 10")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    chunk_minutes = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    create_educational_content_chunks(input_file, output_file, chunk_minutes)
