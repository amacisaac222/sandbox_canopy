#!/usr/bin/env python3
"""
CanopyIQ Security Whitepaper PDF Builder

This script converts the security whitepaper markdown to PDF format using WeasyPrint.
If WeasyPrint is not available, it will provide instructions for manual conversion.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

def check_dependencies():
    """Check if required dependencies are available."""
    try:
        import weasyprint
        import markdown
        import markdown.extensions.toc
        import markdown.extensions.codehilite
        import markdown.extensions.tables
        return True, None
    except ImportError as e:
        return False, str(e)

def install_dependencies():
    """Attempt to install required dependencies."""
    dependencies = [
        "weasyprint",
        "markdown",
        "pygments"  # For syntax highlighting
    ]
    
    print("Installing required dependencies...")
    for dep in dependencies:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"✓ Installed {dep}")
        except subprocess.CalledProcessError:
            print(f"✗ Failed to install {dep}")
            return False
    return True

def get_css_styles():
    """Return CSS styles for the PDF."""
    return """
    @page {
        size: A4;
        margin: 2cm;
        @top-center {
            content: "CanopyIQ Security Whitepaper";
            font-size: 10pt;
            color: #666;
        }
        @bottom-center {
            content: "Page " counter(page) " of " counter(pages);
            font-size: 10pt;
            color: #666;
        }
    }
    
    body {
        font-family: 'Arial', sans-serif;
        font-size: 11pt;
        line-height: 1.6;
        color: #333;
        max-width: none;
    }
    
    h1 {
        color: #1A2E1A;
        border-bottom: 3px solid #D97706;
        padding-bottom: 10px;
        page-break-before: always;
        font-size: 24pt;
        margin-top: 30pt;
    }
    
    h1:first-of-type {
        page-break-before: auto;
        text-align: center;
        margin-top: 50pt;
        margin-bottom: 30pt;
    }
    
    h2 {
        color: #1A2E1A;
        font-size: 18pt;
        margin-top: 25pt;
        margin-bottom: 15pt;
        border-left: 4px solid #D97706;
        padding-left: 15px;
    }
    
    h3 {
        color: #1A2E1A;
        font-size: 14pt;
        margin-top: 20pt;
        margin-bottom: 10pt;
    }
    
    h4 {
        color: #1A2E1A;
        font-size: 12pt;
        margin-top: 15pt;
        margin-bottom: 8pt;
    }
    
    p {
        margin-bottom: 12pt;
        text-align: justify;
    }
    
    code {
        background-color: #f5f5f5;
        padding: 2px 4px;
        border-radius: 3px;
        font-family: 'Courier New', monospace;
        font-size: 10pt;
    }
    
    pre {
        background-color: #f8f8f8;
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 15px;
        overflow-x: auto;
        font-family: 'Courier New', monospace;
        font-size: 9pt;
        line-height: 1.4;
        margin: 15pt 0;
    }
    
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 15pt 0;
        font-size: 10pt;
    }
    
    th, td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
    }
    
    th {
        background-color: #f2f2f2;
        font-weight: bold;
        color: #1A2E1A;
    }
    
    tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    
    blockquote {
        border-left: 4px solid #D97706;
        margin: 15pt 0;
        padding-left: 20px;
        font-style: italic;
        color: #666;
    }
    
    ul, ol {
        margin: 12pt 0;
        padding-left: 30px;
    }
    
    li {
        margin-bottom: 6pt;
    }
    
    .toc {
        page-break-after: always;
        margin-bottom: 30pt;
    }
    
    .toc ul {
        list-style: none;
        padding-left: 0;
    }
    
    .toc li {
        margin-bottom: 8pt;
        padding-left: 20px;
    }
    
    .toc a {
        text-decoration: none;
        color: #1A2E1A;
    }
    
    .toc a:hover {
        color: #D97706;
    }
    
    .page-break {
        page-break-before: always;
    }
    
    .no-break {
        page-break-inside: avoid;
    }
    
    hr {
        border: none;
        border-top: 2px solid #D97706;
        margin: 30pt 0;
    }
    
    .metadata {
        text-align: center;
        color: #666;
        font-size: 10pt;
        margin-bottom: 40pt;
    }
    
    .classification {
        text-align: center;
        font-weight: bold;
        color: #D97706;
        font-size: 12pt;
        margin-bottom: 20pt;
    }
    """

def convert_markdown_to_html(markdown_file, css_styles):
    """Convert markdown to HTML with proper styling."""
    try:
        import markdown
        from markdown.extensions import toc, codehilite, tables
        
        # Read the markdown content
        with open(markdown_file, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # Configure markdown extensions
        extensions = [
            'toc',
            'codehilite',
            'tables',
            'fenced_code',
            'attr_list'
        ]
        
        # Initialize markdown processor
        md = markdown.Markdown(extensions=extensions, extension_configs={
            'toc': {
                'title': 'Table of Contents',
                'anchorlink': True
            },
            'codehilite': {
                'css_class': 'highlight',
                'use_pygments': True
            }
        })
        
        # Convert to HTML
        html_content = md.convert(markdown_content)
        
        # Create complete HTML document
        html_doc = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>CanopyIQ Security Whitepaper</title>
            <style>
                {css_styles}
            </style>
        </head>
        <body>
            <div class="classification">SECURITY WHITEPAPER - PUBLIC</div>
            <div class="metadata">
                Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </div>
            {html_content}
        </body>
        </html>
        """
        
        return html_doc
    
    except Exception as e:
        print(f"Error converting markdown to HTML: {e}")
        return None

def convert_html_to_pdf(html_content, output_file):
    """Convert HTML to PDF using WeasyPrint."""
    try:
        import weasyprint
        
        # Create WeasyPrint HTML object
        html_doc = weasyprint.HTML(string=html_content)
        
        # Generate PDF
        html_doc.write_pdf(output_file)
        return True
    
    except Exception as e:
        print(f"Error converting HTML to PDF: {e}")
        return False

def main():
    """Main function to convert markdown to PDF."""
    # Define paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    docs_dir = repo_root / "docs"
    static_dir = repo_root / "canopyiq_site" / "static"
    
    markdown_file = docs_dir / "security-whitepaper.md"
    pdf_file = static_dir / "security-whitepaper.pdf"
    
    print("CanopyIQ Security Whitepaper PDF Builder")
    print("=" * 50)
    
    # Check if markdown file exists
    if not markdown_file.exists():
        print(f"❌ Markdown file not found: {markdown_file}")
        sys.exit(1)
    
    # Ensure static directory exists
    static_dir.mkdir(parents=True, exist_ok=True)
    
    # Check dependencies
    deps_available, error = check_dependencies()
    
    if not deps_available:
        print(f"❌ Missing dependencies: {error}")
        print("\n🔧 Attempting to install dependencies...")
        
        if not install_dependencies():
            print("\n❌ Failed to install dependencies automatically.")
            print("\n📋 Manual installation instructions:")
            print("   pip install weasyprint markdown pygments")
            print("\n   Note: WeasyPrint may require additional system dependencies:")
            print("   - On Ubuntu/Debian: apt-get install python3-cffi python3-brotli libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0")
            print("   - On macOS: brew install pango")
            print("   - On Windows: Install GTK+ runtime")
            print("\n📄 PDF generation skipped. Markdown file is available at:")
            print(f"   {markdown_file}")
            return
        
        # Re-check dependencies after installation
        deps_available, error = check_dependencies()
        if not deps_available:
            print(f"❌ Dependencies still not available after installation: {error}")
            return
    
    print("✅ All dependencies available")
    
    # Get CSS styles
    css_styles = get_css_styles()
    
    # Convert markdown to HTML
    print("🔄 Converting Markdown to HTML...")
    html_content = convert_markdown_to_html(markdown_file, css_styles)
    
    if not html_content:
        print("❌ Failed to convert Markdown to HTML")
        sys.exit(1)
    
    print("✅ Markdown converted to HTML")
    
    # Convert HTML to PDF
    print("🔄 Converting HTML to PDF...")
    success = convert_html_to_pdf(html_content, pdf_file)
    
    if success:
        print(f"✅ PDF generated successfully: {pdf_file}")
        print(f"📄 File size: {pdf_file.stat().st_size / 1024:.1f} KB")
    else:
        print("❌ Failed to convert HTML to PDF")
        
        # Save HTML file for manual conversion
        html_file = static_dir / "security-whitepaper.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"💾 HTML file saved for manual conversion: {html_file}")
        print("🔧 Manual PDF conversion options:")
        print("   1. Open HTML in browser and print to PDF")
        print("   2. Use pandoc: pandoc security-whitepaper.md -o security-whitepaper.pdf")
        print("   3. Use wkhtmltopdf: wkhtmltopdf security-whitepaper.html security-whitepaper.pdf")
    
    print("\n📚 Files available:")
    print(f"   📄 Markdown: {markdown_file}")
    if pdf_file.exists():
        print(f"   📑 PDF: {pdf_file}")
    
    print("\n🎉 Whitepaper build complete!")

if __name__ == "__main__":
    main()