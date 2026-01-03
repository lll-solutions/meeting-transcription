"""
Tests for parse_text_transcript module.

Test coverage:
- VTT format detection and parsing
- Bracketed timestamp format detection and parsing
- Edge cases: Empty files, malformed timestamps, missing speakers
- Format auto-detection
"""

import pytest
from meeting_transcription.pipeline.parse_text_transcript import (
    detect_text_transcript_format,
    parse_vtt_to_combined_format,
    parse_bracketed_to_combined_format,
    parse_text_to_combined_format,
    parse_timestamp,
    parse_vtt_timestamp
)


class TestTimestampParsing:
    """Tests for timestamp parsing functions."""

    # =========================================================================
    # HAPPY PATH TESTS
    # =========================================================================

    def test_parse_bracketed_mm_ss(self) -> None:
        """Parse MM:SS bracketed timestamp."""
        result = parse_timestamp("[05:30]")
        assert result == 330.0  # 5*60 + 30

    def test_parse_bracketed_hh_mm_ss(self) -> None:
        """Parse HH:MM:SS bracketed timestamp."""
        result = parse_timestamp("[01:23:45]")
        assert result == 5025.0  # 1*3600 + 23*60 + 45

    def test_parse_vtt_timestamp(self) -> None:
        """Parse VTT timestamp with milliseconds."""
        result = parse_vtt_timestamp("00:05:30.500")
        assert result == 330.5  # 5*60 + 30 + 0.5


class TestFormatDetection:
    """Tests for format detection."""

    # =========================================================================
    # VTT FORMAT DETECTION
    # =========================================================================

    def test_detect_vtt_format(self) -> None:
        """VTT format should be detected correctly."""
        vtt_text = """WEBVTT

00:00:05.000 --> 00:00:08.000
Speaker: Hello world
"""
        result = detect_text_transcript_format(vtt_text)

        assert result['is_transcript'] is True
        assert result['format'] == 'vtt'
        assert result['has_timestamps'] is True
        assert result['has_speakers'] is True

    def test_detect_vtt_without_header(self) -> None:
        """VTT without WEBVTT header should not be detected as VTT."""
        text = """00:00:05.000 --> 00:00:08.000
Speaker: Hello world
"""
        result = detect_text_transcript_format(text)

        assert result['format'] != 'vtt'

    # =========================================================================
    # BRACKETED FORMAT DETECTION
    # =========================================================================

    def test_detect_google_meet_format(self) -> None:
        """Google Meet format should be detected."""
        text = """Google Meet Transcript
Session Date: December 17, 2025

[00:00:05]
Speaker: Hello world
"""
        result = detect_text_transcript_format(text)

        assert result['is_transcript'] is True
        assert result['format'] == 'google_meet'

    def test_detect_generic_bracketed_format(self) -> None:
        """Generic bracketed format should be detected."""
        text = """[00:00:05]
Speaker: Hello world

[00:00:10]
Other Speaker: Goodbye
"""
        result = detect_text_transcript_format(text)

        assert result['is_transcript'] is True
        assert result['format'] == 'generic_text'

    # =========================================================================
    # NEGATIVE CASES
    # =========================================================================

    def test_detect_plain_text_not_transcript(self) -> None:
        """Plain text without timestamps should not be detected as transcript."""
        text = "This is just some plain text without any transcript formatting."
        result = detect_text_transcript_format(text)

        assert result['is_transcript'] is False

    def test_detect_timestamps_without_speakers(self) -> None:
        """Text with timestamps but no speakers should not be detected as transcript."""
        text = """[00:00:05]
Just some text without a speaker label
"""
        result = detect_text_transcript_format(text)

        assert result['is_transcript'] is False


class TestVTTParsing:
    """Tests for VTT format parsing."""

    # =========================================================================
    # HAPPY PATH TESTS
    # =========================================================================

    def test_parse_simple_vtt(self) -> None:
        """Parse a simple VTT transcript."""
        vtt_text = """WEBVTT

00:00:05.000 --> 00:00:08.000
Sarah Chen: Good morning everyone

00:00:08.500 --> 00:00:12.000
John Anderson: Morning Sarah
"""
        result = parse_vtt_to_combined_format(vtt_text)

        assert len(result) == 2
        assert result[0]['participant']['name'] == 'Sarah Chen'
        assert result[0]['text'] == 'Good morning everyone'
        assert result[0]['start_timestamp']['relative'] == 5.0
        assert result[0]['end_timestamp']['relative'] == 8.0

        assert result[1]['participant']['name'] == 'John Anderson'
        assert result[1]['text'] == 'Morning Sarah'

    def test_parse_vtt_with_multiline_text(self) -> None:
        """Parse VTT with text spanning multiple lines."""
        vtt_text = """WEBVTT

00:00:05.000 --> 00:00:10.000
Sarah Chen: This is a long statement
that continues on the next line
"""
        result = parse_vtt_to_combined_format(vtt_text)

        assert len(result) == 1
        assert 'long statement' in result[0]['text']
        assert 'next line' in result[0]['text']


class TestBracketedParsing:
    """Tests for bracketed timestamp format parsing."""

    # =========================================================================
    # HAPPY PATH TESTS
    # =========================================================================

    def test_parse_simple_bracketed(self) -> None:
        """Parse a simple bracketed timestamp transcript."""
        text = """[00:00:05]
Sarah Chen: Good morning everyone

[00:00:12]
John Anderson: Morning Sarah
"""
        result = parse_bracketed_to_combined_format(text)

        assert len(result) == 2
        assert result[0]['participant']['name'] == 'Sarah Chen'
        assert result[0]['text'] == 'Good morning everyone'
        assert result[0]['start_timestamp']['relative'] == 5.0
        assert result[0]['end_timestamp']['relative'] == 12.0

        assert result[1]['participant']['name'] == 'John Anderson'

    def test_parse_bracketed_with_multiline_text(self) -> None:
        """Parse bracketed format with text spanning multiple lines."""
        text = """[00:00:05]
Sarah Chen: This is a long statement
that continues on the next line
and even more
"""
        result = parse_bracketed_to_combined_format(text)

        assert len(result) == 1
        assert 'long statement' in result[0]['text']
        assert 'continues on the next line' in result[0]['text']
        assert 'even more' in result[0]['text']

    def test_parse_bracketed_with_mm_ss(self) -> None:
        """Parse bracketed format with MM:SS timestamps (no hours)."""
        text = """[05:30]
Speaker: At 5 minutes 30 seconds
"""
        result = parse_bracketed_to_combined_format(text)

        assert len(result) == 1
        assert result[0]['start_timestamp']['relative'] == 330.0


class TestAutoDetectParsing:
    """Tests for auto-detect parsing function."""

    # =========================================================================
    # HAPPY PATH TESTS
    # =========================================================================

    def test_auto_parse_vtt(self) -> None:
        """Auto-detect and parse VTT format."""
        vtt_text = """WEBVTT

00:00:05.000 --> 00:00:08.000
Speaker: Hello
"""
        result = parse_text_to_combined_format(vtt_text)

        assert len(result) > 0
        assert result[0]['participant']['platform'] == 'zoom'

    def test_auto_parse_bracketed(self) -> None:
        """Auto-detect and parse bracketed format."""
        text = """[00:00:05]
Speaker: Hello
"""
        result = parse_text_to_combined_format(text)

        assert len(result) > 0
        assert result[0]['participant']['name'] == 'Speaker'

    # =========================================================================
    # NEGATIVE CASES
    # =========================================================================

    def test_auto_parse_invalid_format(self) -> None:
        """Auto-parse should raise error for invalid format."""
        text = "This is just plain text"

        with pytest.raises(ValueError, match="valid transcript format"):
            parse_text_to_combined_format(text)


class TestOutputFormat:
    """Tests for combined output format structure."""

    # =========================================================================
    # STRUCTURE VALIDATION
    # =========================================================================

    def test_output_has_required_fields(self) -> None:
        """Parsed output should have all required fields."""
        text = """[00:00:05]
Speaker: Test message
"""
        result = parse_text_to_combined_format(text)

        assert len(result) == 1
        segment = result[0]

        # Check required top-level fields
        assert 'participant' in segment
        assert 'text' in segment
        assert 'start_timestamp' in segment
        assert 'end_timestamp' in segment
        assert 'word_count' in segment

        # Check participant structure
        assert 'id' in segment['participant']
        assert 'name' in segment['participant']
        assert 'is_host' in segment['participant']
        assert 'platform' in segment['participant']

        # Check timestamp structure
        assert 'relative' in segment['start_timestamp']
        assert 'absolute' in segment['start_timestamp']

    def test_word_count_calculated(self) -> None:
        """Word count should be calculated correctly."""
        text = """[00:00:05]
Speaker: One two three four five
"""
        result = parse_text_to_combined_format(text)

        assert result[0]['word_count'] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
