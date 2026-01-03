#!/usr/bin/env python3
"""
Test script for modular pipeline architecture.

This script tests the new modular components (Week 1 deliverable):
- PipelineFactory
- EducationalTimeBasedChunker
- EducationalPromptEngine
- StudyGuideFormatter
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipeline.factories import PipelineFactory
from pipeline.core import ContentType, PromptContext


def test_pipeline_factory():
    """Test PipelineFactory content type detection and configuration creation."""
    print("\n=== Testing PipelineFactory ===\n")

    # Test 1: Default content type (educational)
    config = PipelineFactory.create_pipeline_from_hint()
    assert config.content_type == ContentType.EDUCATIONAL
    print("✓ Test 1: Default content type is educational")

    # Test 2: Explicit hint
    config = PipelineFactory.create_pipeline_from_hint(content_type_hint='educational')
    assert config.content_type == ContentType.EDUCATIONAL
    print("✓ Test 2: Explicit 'educational' hint works")

    # Test 3: Metadata-based detection (educational)
    metadata = {'instructor': 'Dr. Smith', 'course_id': 'CS101'}
    config = PipelineFactory.create_pipeline_from_hint(metadata=metadata)
    assert config.content_type == ContentType.EDUCATIONAL
    print("✓ Test 3: Metadata-based detection (educational) works")

    # Test 4: Verify config has correct components
    assert config.chunker_class.__name__ == 'EducationalTimeBasedChunker'
    assert config.prompt_engine_class.__name__ == 'EducationalPromptEngine'
    assert config.formatter_class.__name__ == 'StudyGuideFormatter'
    print("✓ Test 4: Config has correct component classes")

    # Test 5: Custom parameters
    config = PipelineFactory.create_pipeline_from_hint(
        chunk_minutes=15,
        generate_pdf=False
    )
    assert config.chunker_params['chunk_minutes'] == 15
    assert config.generate_pdf == False
    print("✓ Test 5: Custom parameters work")

    print("\n✅ All PipelineFactory tests passed!")


def test_educational_chunker():
    """Test EducationalTimeBasedChunker with sample data."""
    print("\n=== Testing EducationalTimeBasedChunker ===\n")

    from pipeline.chunkers import EducationalTimeBasedChunker

    # Create sample transcript (minimal realistic structure)
    sample_transcript = [
        {
            'participant': {'name': 'Dr. Smith'},
            'text': 'Welcome to today\'s class on RAG architecture.',
            'word_count': 8,
            'start_timestamp': {'relative': 0.0},
            'end_timestamp': {'relative': 5.0}
        },
        {
            'participant': {'name': 'Dr. Smith'},
            'text': 'Let me explain how vector databases work.',
            'word_count': 8,
            'start_timestamp': {'relative': 5.0},
            'end_timestamp': {'relative': 10.0}
        },
        {
            'participant': {'name': 'Student Alice'},
            'text': 'Can you explain the difference between semantic and keyword search?',
            'word_count': 11,
            'start_timestamp': {'relative': 610.0},  # 10 minutes later
            'end_timestamp': {'relative': 615.0}
        },
        {
            'participant': {'name': 'Dr. Smith'},
            'text': 'Great question! Semantic search uses embeddings...',
            'word_count': 7,
            'start_timestamp': {'relative': 615.0},
            'end_timestamp': {'relative': 620.0}
        }
    ]

    # Test 1: Create chunker
    chunker = EducationalTimeBasedChunker(chunk_minutes=10)
    print("✓ Test 1: Chunker instantiated")

    # Test 2: Chunk transcript
    result = chunker.chunk_transcript(sample_transcript)
    print(f"✓ Test 2: Transcript chunked into {result['metadata'].total_chunks} chunks")

    # Test 3: Verify metadata
    metadata = result['metadata']
    assert metadata.content_type == ContentType.EDUCATIONAL
    assert metadata.chunk_strategy.value == 'time_based'
    assert metadata.total_chunks >= 1
    print("✓ Test 3: Metadata is correct")

    # Test 4: Verify chunks have correct structure
    chunks = result['chunks']
    assert len(chunks) > 0
    assert 'chunk_number' in chunks[0]
    assert 'segments' in chunks[0]
    assert 'instructor_words' in chunks[0]
    print("✓ Test 4: Chunks have correct structure")

    # Test 5: Verify instructor identified correctly
    assert metadata.additional_metadata['instructor'] == 'Dr. Smith'
    print("✓ Test 5: Instructor identified correctly")

    print("\n✅ All EducationalChunker tests passed!")


def test_educational_prompt_engine():
    """Test EducationalPromptEngine."""
    print("\n=== Testing EducationalPromptEngine ===\n")

    from pipeline.prompts import EducationalPromptEngine

    # Test 1: Create prompt engine
    engine = EducationalPromptEngine()
    print("✓ Test 1: Prompt engine instantiated")

    # Test 2: Verify context injection not supported
    assert engine.supports_context_injection() == False
    print("✓ Test 2: Context injection correctly set to False")

    # Test 3: Create sample chunk and context
    chunk = {
        'chunk_number': 1,
        'time_range': '00:00 - 10:00',
        'duration_minutes': 10.0,
        'speakers': ['Dr. Smith', 'Student Alice'],
        'has_student_interaction': True,
        'segments': [
            {
                'speaker': 'Dr. Smith',
                'is_instructor': True,
                'text': 'Today we discuss RAG.',
                'timestamp': '00:00',
                'word_count': 5
            }
        ]
    }

    context = PromptContext(
        content_type=ContentType.EDUCATIONAL,
        session_metadata={'instructor': 'Dr. Smith'}
    )

    # Test 4: Generate chunk analysis prompt
    prompt = engine.create_chunk_analysis_prompt(chunk, context)
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert 'Dr. Smith' in prompt
    print("✓ Test 3: Chunk analysis prompt generated")

    print("\n✅ All EducationalPromptEngine tests passed!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("MODULAR PIPELINE ARCHITECTURE TEST")
    print("Testing Week 1 Deliverables")
    print("=" * 60)

    try:
        test_pipeline_factory()
        test_educational_chunker()
        test_educational_prompt_engine()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nWeek 1 Foundation is complete:")
        print("  ✓ Abstract base classes implemented")
        print("  ✓ Educational wrappers working")
        print("  ✓ Pipeline factory functional")
        print("\nNext steps:")
        print("  - Week 2: Implement therapy-specific components")
        print("  - Week 3: Add database integration")
        print("  - Week 4: Integrate with main.py")
        print("")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
