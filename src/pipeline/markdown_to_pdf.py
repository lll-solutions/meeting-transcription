#!/usr/bin/env python3
"""
Convert Markdown to PDF with nice formatting.
"""
import sys
import os
import subprocess

def markdown_to_html(md_file, html_file):
    """Convert markdown to HTML with nice styling."""
    with open(md_file, 'r') as f:
        content = f.read()

    # Try to use markdown library
    try:
        import markdown
        html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
    except ImportError:
        # Fallback: basic conversion
        html_content = content.replace('\n', '<br>\n')

    # Create HTML with nice CSS
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Study Guide</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 40px auto;
            padding: 20px;
            color: #333;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 5px;
        }}
        h3 {{
            color: #7f8c8d;
            margin-top: 20px;
        }}
        ul, ol {{
            margin-left: 20px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        table, th, td {{
            border: 1px solid #ddd;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background-color: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        blockquote {{
            border-left: 4px solid #3498db;
            margin: 20px 0;
            padding-left: 20px;
            color: #555;
        }}
        hr {{
            border: none;
            border-top: 2px solid #ecf0f1;
            margin: 30px 0;
        }}
        @media print {{
            body {{
                margin: 0;
                padding: 20px;
            }}
            h1 {{
                page-break-before: always;
            }}
            h1:first-child {{
                page-break-before: avoid;
            }}
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""

    with open(html_file, 'w') as f:
        f.write(html)

    print(f"✓ Created HTML: {html_file}")

def html_to_pdf_chrome(html_file, pdf_file):
    """Use Chrome to convert HTML to PDF."""
    chrome_paths = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
        'google-chrome',
        'chromium',
        'chromium-browser'
    ]

    for chrome in chrome_paths:
        try:
            cmd = [
                chrome,
                '--headless',
                '--disable-gpu',
                '--print-to-pdf=' + pdf_file,
                html_file
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            print(f"✓ Created PDF: {pdf_file}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue

    return False

def convert_markdown_to_pdf(md_file, output_pdf=None):
    """Convert markdown file to PDF.
    
    Args:
        md_file: Path to markdown file
        output_pdf: Optional output PDF path (defaults to same name as md_file)
    """
    base_name = md_file.replace('.md', '')
    html_file = f"{base_name}.html"
    pdf_file = output_pdf or f"{base_name}.pdf"

    # Convert to HTML
    markdown_to_html(md_file, html_file)

    # Convert to PDF
    if html_to_pdf_chrome(html_file, pdf_file):
        # Keep HTML file for reference
        print(f"✓ HTML file saved: {html_file}")
        return pdf_file
    else:
        print(f"✗ Failed to create PDF from {md_file}")
        print("Make sure Google Chrome is installed")
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
