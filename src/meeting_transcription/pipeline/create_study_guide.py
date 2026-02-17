#!/usr/bin/env python3
"""
Create markdown and PDF study guide from educational summary JSON.
"""
import json
import sys
from datetime import datetime


def create_markdown_study_guide(summary_file: str, output_file: str):
    """
    Convert educational summary JSON to markdown study guide.

    Args:
        summary_file: Path to summary JSON
        output_file: Path to output markdown file
    """
    # Load summary
    with open(summary_file) as f:
        data = json.load(f)

    metadata = data.get('metadata', {})
    chunk_analyses = data.get('chunk_analyses', [])
    overall_summary = data.get('overall_summary', {})
    action_items = data.get('action_items', {})

    # Start building markdown
    md = []

    # Title
    class_topic = overall_summary.get('class_metadata', {}).get('topic', 'AI Solutions Architect Class')
    md.append(f"# {class_topic}")
    md.append("")

    # Metadata
    md.append("## Class Information")
    md.append("")
    md.append(f"- **Instructor**: {metadata.get('instructor', 'Unknown')}")
    md.append(f"- **Date**: {metadata.get('meeting_date', 'Unknown')}")
    md.append(f"- **Duration**: {metadata.get('meeting_duration_minutes', 0)} minutes")
    md.append(f"- **Participants**: {metadata.get('total_participants', 0)}")
    md.append("")

    # Executive Summary
    if 'executive_summary' in overall_summary and overall_summary['executive_summary']:
        md.append("## Executive Summary")
        md.append("")
        md.append(overall_summary['executive_summary'])
        md.append("")

    # Action Items
    md.append("## Action Items")
    md.append("")

    if action_items:
        if action_items.get('student_assignments'):
            md.append("### Student Assignments")
            md.append("")
            for assignment in action_items['student_assignments']:
                md.append(f"- **{assignment.get('assignment', 'Task')}**")
                if assignment.get('due_date'):
                    md.append(f"  - Due: {assignment['due_date']}")
                if assignment.get('purpose'):
                    md.append(f"  - Purpose: {assignment['purpose']}")
                md.append("")

        if action_items.get('instructor_commitments'):
            md.append("### Instructor Commitments")
            md.append("")
            for commit in action_items['instructor_commitments']:
                md.append(f"- {commit.get('commitment', 'Task')}")
                if commit.get('timeline'):
                    md.append(f"  - Timeline: {commit['timeline']}")
                md.append("")

        if action_items.get('preparation_for_next_class'):
            md.append("### Preparation for Next Class")
            md.append("")
            for prep in action_items['preparation_for_next_class']:
                md.append(f"- {prep.get('task', 'Task')}")
                if prep.get('reason'):
                    md.append(f"  - Reason: {prep['reason']}")
                md.append("")

    # Table of Contents
    md.append("## Table of Contents")
    md.append("")
    md.append("1. [Action Items](#action-items)")
    md.append("2. [Best Practices](#best-practices)")
    md.append("3. [Unique Insights](#unique-insights)")
    md.append("4. [Tools & Frameworks](#tools--frameworks)")
    md.append("5. [Q&A Exchanges](#qa-exchanges)")
    md.append("6. [Class Timeline](#class-timeline)")
    md.append("7. [Key Concepts](#key-concepts)")
    md.append("")

    # Get best practices from overall summary (already deduplicated)
    best_practices = overall_summary.get('best_practices_learned', [])

    # Best Practices
    md.append("## Best Practices")
    md.append("")
    if not best_practices:
        md.append("*No best practices were identified in this session.*")
        md.append("")
    else:
        for i, practice_obj in enumerate(best_practices, 1):
            if isinstance(practice_obj, dict):
                practice = practice_obj.get('practice', '').strip()
                context = practice_obj.get('context', '').strip()
                importance = practice_obj.get('importance', '').strip()

                # Handle case where practice might be empty but context/importance exist
                if not practice and (context or importance):
                    practice = "(Untitled Practice)"

                # Always show the practice title in bold for better formatting
                md.append(f"{i}. **{practice}**")

                # Add context and importance if they exist
                if context:
                    md.append(f"   - *Context*: {context}")
                if importance:
                    md.append(f"   - *Why it matters*: {importance}")

                # Add blank line between practices for readability
                md.append("")
            else:
                # Fallback if it's just a string (shouldn't happen with updated prompt)
                md.append(f"{i}. {str(practice_obj).strip()}")
                md.append("")

    # Get unique insights from overall summary (already deduplicated)
    unique_insights = overall_summary.get('unique_insights', [])

    # Unique Insights
    if unique_insights:
        md.append("## Unique Insights")
        md.append("")
        md.append("*Distinctive wisdom, counterintuitive advice, and \"obvious but neglected\" practices shared by the instructor:*")
        md.append("")
        for i, insight in enumerate(unique_insights, 1):
            md.append(f"{i}. {insight}")
        md.append("")
    # Collect all unique concepts (to be rendered later at the end)
    all_concepts = {}
    for chunk in chunk_analyses:
        for concept in chunk.get('key_concepts', []):
            name = concept.get('name', 'Unknown')
            if name not in all_concepts:
                all_concepts[name] = {
                    'definition': concept.get('definition', ''),
                    'explanation': concept.get('explanation_summary', ''),
                    'examples': concept.get('examples_mentioned', []),
                    'chunks': []
                }
            all_concepts[name]['chunks'].append(chunk['chunk_number'])
    # Collect all unique tools
    all_tools = {}
    for chunk in chunk_analyses:
        for tool in chunk.get('tools_frameworks', []):
            name = tool.get('name', 'Unknown')
            if name not in all_tools:
                all_tools[name] = {
                    'context': tool.get('context', ''),
                    'use_case': tool.get('use_case', ''),
                    'chunks': []
                }
            all_tools[name]['chunks'].append(chunk['chunk_number'])
    # Tools & Frameworks
    md.append("## Tools & Frameworks")
    md.append("")
    md.append("| Tool/Framework | Purpose | Use Case |")
    md.append("|----------------|---------|----------|")
    for name, details in sorted(all_tools.items()):
        context = details['context'].replace('\n', ' ')[:100]
        use_case = details['use_case'].replace('\n', ' ')[:100]
        md.append(f"| **{name}** | {context} | {use_case} |")
    md.append("")

    # Collect all Q&A
    all_qa = []
    for chunk in chunk_analyses:
        for qa in chunk.get('qa_exchanges', []):
            qa['chunk'] = chunk['chunk_number']
            qa['time_range'] = chunk['time_range']
            all_qa.append(qa)

    # Consolidate duplicate questions
    if len(all_qa) > 3:
        print("🔄 Consolidating Q&A exchanges...")
        # Group by similar questions
        consolidated_qa = []
        seen_questions = {}

        for qa in all_qa:
            question = qa.get('question', '')
            # Simple similarity check - questions with 80%+ word overlap are considered duplicates
            is_duplicate = False
            for seen_q in seen_questions:
                q_words = set(question.lower().split())
                seen_words = set(seen_q.lower().split())
                if len(q_words & seen_words) / max(len(q_words), len(seen_words)) > 0.8:
                    is_duplicate = True
                    break

            if not is_duplicate:
                consolidated_qa.append(qa)
                seen_questions[question] = True

        print(f"  Consolidated {len(all_qa)} → {len(consolidated_qa)} Q&A exchanges")
        all_qa = consolidated_qa

    # Q&A Exchanges
    if all_qa:
        md.append("## Q&A Exchanges")
        md.append("")
        for i, qa in enumerate(all_qa, 1):
            md.append(f"### Q{i}: {qa.get('question', 'Question')}")
            md.append("")
            timestamp = qa.get('timestamp', qa.get('time_range', 'Unknown'))
            md.append(f"**Time**: {timestamp}")
            md.append("")
            md.append(f"**Answer**: {qa.get('answer_summary', 'No answer summary')}")
            md.append("")

    # Class Timeline
    md.append("## Class Timeline")
    md.append("")
    for chunk in chunk_analyses:
        md.append(f"### {chunk['time_range']}")
        md.append("")
        md.append(f"**Main Theme**: {chunk.get('main_theme', 'No theme')}")
        md.append("")

        if chunk.get('key_concepts'):
            md.append("**Concepts Covered**:")
            for concept in chunk['key_concepts']:
                md.append(f"- {concept.get('name', 'Unknown')}")
            md.append("")

        if chunk.get('tools_frameworks'):
            md.append("**Tools Mentioned**:")
            for tool in chunk['tools_frameworks'][:5]:  # Limit to 5
                md.append(f"- {tool.get('name', 'Unknown')}")
            md.append("")

    # Key Concepts (at the end as requested)
    md.append("## Key Concepts")
    md.append("")
    for i, (name, details) in enumerate(sorted(all_concepts.items()), 1):
        md.append(f"### {i}. {name}")
        md.append("")
        if details['definition']:
            md.append(f"**Definition**: {details['definition']}")
            md.append("")
        if details['explanation']:
            md.append(f"**Explanation**: {details['explanation']}")
            md.append("")
        if details['examples']:
            md.append("**Examples**:")
            for ex in details['examples']:
                md.append(f"- {ex}")
            md.append("")
        md.append(f"*Covered in: Chunk(s) {', '.join(map(str, details['chunks']))}*")
        md.append("")

    # Footer
    md.append("---")
    md.append("")
    md.append(f"*Study guide generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    md.append("")

    # Write markdown
    markdown_content = '\n'.join(md)
    with open(output_file, 'w') as f:
        f.write(markdown_content)

    print(f"✓ Markdown study guide created: {output_file}")

    # Calculate stats
    total_concepts = len(all_concepts)
    total_tools = len(all_tools)
    total_practices = len(best_practices)
    total_insights = len(unique_insights)
    total_qa = len(all_qa)

    print("\nStudy Guide Contents:")
    print(f"  - {total_concepts} Key Concepts")
    print(f"  - {total_tools} Tools/Frameworks")
    print(f"  - {total_practices} Best Practices")
    print(f"  - {total_insights} Unique Insights")
    print(f"  - {total_qa} Q&A Exchanges")
    print(f"  - {len(chunk_analyses)} Time Segments")

    return output_file


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python create_study_guide.py <summary_json> <output_md>")
        print("\nExample:")
        print("  python create_study_guide.py transcript_summary.json study_guide.md")
        sys.exit(1)

    summary_file = sys.argv[1]
    output_file = sys.argv[2]

    create_markdown_study_guide(summary_file, output_file)
