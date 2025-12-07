#!/usr/bin/env python3
"""
Combine individual words in transcript into full text segments.
"""
import json
import sys

def combine_transcript_words(input_file, output_file):
    """
    Transform transcript from word-level to conversation-level.

    Args:
        input_file: Path to input JSON file with individual words
        output_file: Path to output JSON file with combined text
    """
    # Read the transcript
    with open(input_file, 'r') as f:
        transcript = json.load(f)

    # Transform each segment
    combined_transcript = []
    for segment in transcript:
        # Combine all words into a single text string
        words = segment.get('words', [])

        if not words:
            continue

        combined_text = ' '.join(word['text'] for word in words)

        # Create new segment structure
        combined_segment = {
            'participant': segment['participant'],
            'text': combined_text,
            'start_timestamp': words[0]['start_timestamp'],
            'end_timestamp': words[-1]['end_timestamp'],
            'word_count': len(words)
        }

        combined_transcript.append(combined_segment)

    # Write the combined transcript
    with open(output_file, 'w') as f:
        json.dump(combined_transcript, f, indent=2)

    print(f"Processed {len(combined_transcript)} segments")
    print(f"Output written to: {output_file}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python combine_transcript_words.py <input_file> <output_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    combine_transcript_words(input_file, output_file)
