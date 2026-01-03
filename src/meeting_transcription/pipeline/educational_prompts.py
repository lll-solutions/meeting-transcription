#!/usr/bin/env python3
"""
LLM prompt templates for educational content extraction.
Designed for AI/tech class recordings.
"""

# Prompt for analyzing individual chunks
CHUNK_ANALYSIS_PROMPT = """You are analyzing a transcript chunk from an AI Solutions Architect class taught by {instructor}.

Your task is to extract structured educational content from this transcript segment.

TRANSCRIPT CHUNK:
{chunk_text}

Extract the following information in JSON format:

1. **key_concepts**: List of technical concepts explained in this segment
   - For each concept include: name, definition, explanation_summary, examples_mentioned

2. **technical_topics**: Specific technical topics discussed
   - For each topic include: name, key_points (list), tools_mentioned (list)

3. **qa_exchanges**: Any question-answer exchanges between students and instructor
   - For each Q&A include: question, asked_by, answer_summary, timestamp

4. **tools_frameworks**: Any tools, frameworks, or technologies mentioned
   - For each include: name, context (how it was discussed), use_case

5. **code_examples**: Any code examples or technical demonstrations mentioned
   - Include: topic, language (if specified), summary

6. **assignments_tasks**: Any homework, assignments, or action items given

7. **resources**: Any articles, links, documentation, or resources mentioned

8. **main_theme**: 1-2 sentence summary of what this chunk was primarily about

Note: Best practices and unique insights will be extracted from the full transcript analysis, not per-chunk.

Return ONLY valid JSON. If a category has no content, return an empty list/string.

Example response structure:
{{
  "main_theme": "Introduction to RAG architecture and vector databases",
  "key_concepts": [
    {{
      "name": "RAG (Retrieval Augmented Generation)",
      "definition": "Technique to enhance LLM responses with retrieved context",
      "explanation_summary": "Instructor explained how RAG combines...",
      "examples_mentioned": ["Customer support chatbot", "Document Q&A"]
    }}
  ],
  "technical_topics": [
    {{
      "name": "Vector Databases",
      "key_points": ["Store embeddings", "Enable semantic search"],
      "tools_mentioned": ["Pinecone", "Weaviate"]
    }}
  ],
  "qa_exchanges": [
    {{
      "question": "How do you choose chunk size?",
      "asked_by": "René Clayton",
      "answer_summary": "Depends on document type...",
      "timestamp": "15:30"
    }}
  ],
  "tools_frameworks": [
    {{
      "name": "LangChain",
      "context": "Building RAG pipelines",
      "use_case": "Orchestrating LLM workflows"
    }}
  ],
  "code_examples": [
    {{
      "topic": "Creating embeddings",
      "language": "Python",
      "summary": "Demonstrated OpenAI API for embeddings"
    }}
  ],
  "assignments_tasks": [
    "Implement basic RAG system using LangChain"
  ],
  "resources": [
    {{
      "type": "documentation",
      "name": "LangChain RAG Tutorial",
      "reference": "Shared in chat"
    }}
  ]
}}
"""

# Prompt for creating overall summary from all chunks
OVERALL_SUMMARY_PROMPT = """You are creating a comprehensive study guide for an AI Solutions Architect class.

You have analyzed {num_chunks} chunks of the class recording. Below is the extracted information from each chunk.

CHUNK SUMMARIES:
{chunk_summaries}

Your task is to create a comprehensive educational summary in JSON format with the following structure:

{{
  "class_metadata": {{
    "topic": "Main topic/title for this class session",
    "instructor": "{instructor}",
    "duration_minutes": {duration},
    "date": "{date}",
    "participants": {num_participants}
  }},

  "executive_summary": "2-3 paragraph overview of the entire class session",

  "learning_objectives": [
    "List of main learning objectives covered in the class"
  ],

  "key_concepts": [
    {{
      "concept": "Concept name",
      "definition": "Clear definition",
      "when_covered": "Time range or chunk reference",
      "explanation": "Detailed explanation from class",
      "examples": ["Examples provided"],
      "related_concepts": ["Related concept names"]
    }}
  ],

  "technical_topics": [
    {{
      "topic": "Topic name",
      "coverage": "How thoroughly this was covered",
      "key_points": ["Main points discussed"],
      "tools_mentioned": ["Relevant tools/frameworks"],
      "when_discussed": "Time references"
    }}
  ],

  "qa_summary": {{
    "total_questions": "Number of student questions",
    "main_topics_asked_about": ["Topics students asked about"],
    "detailed_qa": [
      {{
        "question": "Question text",
        "asked_by": "Student name",
        "answer": "Summary of answer",
        "timestamp": "When asked"
      }}
    ]
  }},

  "tools_frameworks_covered": [
    {{
      "name": "Tool/framework name",
      "purpose": "What it's used for",
      "how_covered": "Demo, discussion, or mention",
      "key_takeaways": ["What students should know about it"]
    }}
  ],

  "best_practices_learned": [
    {{
      "practice": "Short, memorable title for the best practice (e.g., 'Snap the Chalk Line', 'The Neural Network First Rule')",
      "context": "Specific scenario or situation where this applies (e.g., 'Project Kickoff', 'When using AI for planning')",
      "importance": "Clear explanation of why this matters and what it prevents/enables (2-3 sentences)"
    }}
  ],

  "code_demonstrations": [
    {{
      "what_was_shown": "Description",
      "language_platform": "Tech used",
      "key_learning": "What students should take away",
      "timestamp": "When shown"
    }}
  ],

  "assignments_homework": [
    {{
      "assignment": "What to do",
      "purpose": "Why this assignment",
      "due_date": "When due (if mentioned)",
      "resources_needed": ["What students need"]
    }}
  ],

  "resources_shared": [
    {{
      "resource": "Resource name/description",
      "type": "Article, video, documentation, etc.",
      "relevance": "How it relates to class",
      "access": "How to access (if mentioned)"
    }}
  ],

  "class_flow": [
    {{
      "time_range": "Time period",
      "activity": "What happened in this period",
      "key_points": ["Main takeaways from this section"]
    }}
  ],

  "student_engagement_highlights": [
    "Notable moments of student participation, questions, or discussions"
  ],

  "unique_insights": [
    "Counterintuitive advice, personal stories with lessons, or 'obvious but neglected' wisdom shared by the instructor. DEDUPLICATE aggressively - aim for 10-15 unique insights, not 40+."
  ],

  "next_steps": {{
    "preview_next_class": "What's coming next (if mentioned)",
    "what_to_review": ["Topics to review before next class"],
    "action_items": ["Things students should do"]
  }}
}}

Important:
- **AGGRESSIVELY DEDUPLICATE**: If the same concept/practice/insight appears in multiple chunks with slightly different wording, consolidate it into ONE entry. Do NOT create separate entries for minor rewordings of the same idea.
- For best_practices_learned: Aim for 8-12 UNIQUE practices maximum. If "write goals daily" appears 5 times, create ONE entry, not five.
- For unique_insights: Aim for 10-15 UNIQUE insights maximum. Merge similar insights even if worded differently.
- Maintain chronological flow where relevant
- Highlight the most important concepts (mentioned multiple times or emphasized by instructor)
- Make this useful as a study guide for students who attended OR missed the class
- Be specific with technical details - this is a technical class
"""

# Prompt for extracting action items across entire transcript
ACTION_ITEMS_PROMPT = """You are analyzing a transcript from an AI Solutions Architect class to extract ALL action items, assignments, and commitments.

FULL TRANSCRIPT SUMMARY:
{full_summary}

Extract:

1. **Student Assignments**: Homework, projects, tasks assigned to students
2. **Instructor Commitments**: Things the instructor promised to share/do
3. **Class Expectations**: What students should do before next class
4. **Resource Sharing**: Materials that will be shared or were mentioned

Return in JSON format:
{{
  "student_assignments": [
    {{
      "assignment": "Description",
      "due_date": "When due",
      "purpose": "Why assigned",
      "mentioned_at": "Timestamp"
    }}
  ],
  "instructor_commitments": [
    {{
      "commitment": "What instructor will do",
      "timeline": "When",
      "mentioned_at": "Timestamp"
    }}
  ],
  "preparation_for_next_class": [
    {{
      "task": "What to do",
      "reason": "Why it's important"
    }}
  ],
  "resources_to_be_shared": [
    {{
      "resource": "What will be shared",
      "how": "Method of sharing (Slack, email, etc.)",
      "mentioned_at": "Timestamp"
    }}
  ]
}}
"""

# Helper function to format chunk for LLM
def format_chunk_for_llm_analysis(chunk_data, instructor):
    """Format a single chunk for LLM analysis."""
    chunk_text = f"=== TIME RANGE: {chunk_data['time_range']} ===\n"
    chunk_text += f"Duration: {chunk_data['duration_minutes']:.1f} minutes\n"
    chunk_text += f"Speakers: {', '.join(chunk_data['speakers'])}\n"
    chunk_text += f"Student Interaction: {'Yes' if chunk_data['has_student_interaction'] else 'No'}\n\n"
    chunk_text += "TRANSCRIPT:\n\n"

    for seg in chunk_data['segments']:
        role = "INSTRUCTOR" if seg['is_instructor'] else "STUDENT"
        chunk_text += f"[{seg['timestamp']}] {role} ({seg['speaker']}): {seg['text']}\n\n"

    return CHUNK_ANALYSIS_PROMPT.format(
        instructor=instructor,
        chunk_text=chunk_text
    )

def create_overall_summary_prompt(chunk_analyses, metadata):
    """Create prompt for overall summary from chunk analyses."""
    chunk_summaries_text = ""
    for i, analysis in enumerate(chunk_analyses, 1):
        chunk_summaries_text += f"\n=== CHUNK {i} ===\n{analysis}\n"

    return OVERALL_SUMMARY_PROMPT.format(
        num_chunks=len(chunk_analyses),
        chunk_summaries=chunk_summaries_text,
        instructor=metadata.get('instructor', 'Unknown'),
        duration=metadata.get('meeting_duration_minutes', 0),
        date=metadata.get('meeting_date', 'Unknown'),
        num_participants=metadata.get('total_participants', 0)
    )

def create_action_items_prompt(overall_summary):
    """Create prompt for extracting action items."""
    return ACTION_ITEMS_PROMPT.format(full_summary=overall_summary)

if __name__ == '__main__':
    # Example usage
    print("Educational prompt templates loaded.")
    print("\nAvailable prompts:")
    print("1. CHUNK_ANALYSIS_PROMPT - Analyze individual chunks")
    print("2. OVERALL_SUMMARY_PROMPT - Create comprehensive summary")
    print("3. ACTION_ITEMS_PROMPT - Extract action items")
