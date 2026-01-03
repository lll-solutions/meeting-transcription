#!/usr/bin/env python3
"""
Convert Markdown to PDF with nice formatting using WeasyPrint.
"""
import sys
import os

def convert_markdown_to_pdf(md_file, output_pdf=None):
    """Convert markdown file to PDF.

    Args:
        md_file: Path to markdown file
        output_pdf: Optional output PDF path (defaults to same name as md_file)

    Returns:
        str: Path to generated PDF file, or None if failed
    """
    try:
        import markdown
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
    except ImportError as e:
        print(f"✗ Missing required library: {e}")
        print("Install with: pip install markdown weasyprint")
        return None

    # Read markdown content
    with open(md_file, 'r') as f:
        md_content = f.read()

    # Convert markdown to HTML
    html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])

    # Create styled HTML document
    styled_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Study Guide</title>
    <style>
        @page {{
            size: letter;
            margin: 1in;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            font-size: 11pt;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            font-size: 24pt;
            margin-top: 0;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 5px;
            font-size: 18pt;
            page-break-after: avoid;
        }}
        h3 {{
            color: #7f8c8d;
            margin-top: 20px;
            font-size: 14pt;
            page-break-after: avoid;
        }}
        ul, ol {{
            margin-left: 20px;
        }}
        li {{
            margin-bottom: 5px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
            page-break-inside: avoid;
        }}
        table, th, td {{
            border: 1px solid #ddd;
        }}
        th, td {{
            padding: 8px 12px;
            text-align: left;
        }}
        th {{
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }}
        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 10pt;
        }}
        pre {{
            background-color: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            page-break-inside: avoid;
        }}
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        blockquote {{
            border-left: 4px solid #3498db;
            margin: 20px 0;
            padding-left: 20px;
            color: #555;
            font-style: italic;
        }}
        hr {{
            border: none;
            border-top: 2px solid #ecf0f1;
            margin: 30px 0;
        }}
        p {{
            margin-bottom: 10px;
            orphans: 3;
            widows: 3;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""

    # Generate PDF
    pdf_file = output_pdf or md_file.replace('.md', '.pdf')

    try:
        font_config = FontConfiguration()
        HTML(string=styled_html).write_pdf(
            pdf_file,
            font_config=font_config
        )
        print(f"✓ Created PDF: {pdf_file}")
        return pdf_file
    except Exception as e:
        print(f"✗ Failed to create PDF: {e}")
        return None

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python markdown_to_pdf.py <input.md>")
        print("\nExample:")
        print("  python markdown_to_pdf.py study_guide.md")
        sys.exit(1)

    md_file = sys.argv[1]

    if not os.path.exists(md_file):
        print(f"✗ File not found: {md_file}")
        sys.exit(1)

    print(f"Converting: {md_file}")
    pdf_file = convert_markdown_to_pdf(md_file)

    if pdf_file:
        print(f"\n{'=' * 60}")
        print(f"Success! PDF created: {pdf_file}")
    else:
        sys.exit(1)
