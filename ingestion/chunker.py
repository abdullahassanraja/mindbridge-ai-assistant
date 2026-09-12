import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Chunk:
    text: str
    doc_title: str
    section_title: str
    source_file: str
    metadata: dict = field(default_factory=dict)


def _pack_paragraphs(paragraphs: List[str], max_chars: int = 1200) -> List[str]:
    """Greedily pack paragraphs up to max_chars characters."""
    packed_chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for para in paragraphs:
        cleaned = para.strip()
        if not cleaned:
            continue
        para_len = len(cleaned)
        # Separator length when joining with "\n\n"
        sep_len = 2 if current_chunk else 0

        if current_chunk and (current_len + sep_len + para_len > max_chars):
            packed_chunks.append("\n\n".join(current_chunk))
            current_chunk = [cleaned]
            current_len = para_len
        else:
            current_chunk.append(cleaned)
            current_len += sep_len + para_len

    if current_chunk:
        packed_chunks.append("\n\n".join(current_chunk))

    return packed_chunks


def _clean_markdown_dividers(text: str) -> str:
    """Remove trailing or standalone markdown dividers like --- or ***."""
    lines = [line for line in text.splitlines() if not re.match(r'^\s*[-*_]{3,}\s*$', line)]
    return "\n".join(lines).strip()


def chunk_markdown_text(text: str, source_name: str) -> List[Chunk]:
    """Chunk raw markdown text using H1 as doc_title and H2 (##) or bold FAQs as sections."""
    chunks: List[Chunk] = []

    # 1. Extract H1 doc title if present
    h1_match = re.search(r'^#\s+(.+)$', text, flags=re.MULTILINE)
    if h1_match:
        doc_title = h1_match.group(1).strip()
        # Remove the first H1 line from content so it isn't duplicated
        content = text[:h1_match.start()] + text[h1_match.end():]
    else:
        # Fallback doc_title from source name
        stem = Path(source_name).stem
        doc_title = stem.replace('_', ' ').replace('-', ' ').title()
        content = text

    content = content.strip()

    # 2. Check for H2 (##) headers
    h2_matches = list(re.finditer(r'(?m)^##\s+(.+)$', content))

    if h2_matches:
        # Check if there is an introductory section before the first H2
        first_h2_start = h2_matches[0].start()
        intro_text = _clean_markdown_dividers(content[:first_h2_start].strip())
        if intro_text:
            if len(intro_text) > 1200:
                paras = re.split(r'\n\s*\n', intro_text)
                packed = _pack_paragraphs(paras, max_chars=1200)
                for p in packed:
                    chunk_text = f"{doc_title} — Overview\n\n{p}"
                    chunks.append(Chunk(
                        text=chunk_text,
                        doc_title=doc_title,
                        section_title="Overview",
                        source_file=source_name,
                        metadata={}
                    ))
            else:
                chunk_text = f"{doc_title} — Overview\n\n{intro_text}"
                chunks.append(Chunk(
                    text=chunk_text,
                    doc_title=doc_title,
                    section_title="Overview",
                    source_file=source_name,
                    metadata={}
                ))

        # Process each H2 section
        for i, match in enumerate(h2_matches):
            section_title = match.group(1).strip()
            section_start = match.end()
            section_end = h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(content)
            section_body = _clean_markdown_dividers(content[section_start:section_end].strip())

            if not section_body:
                continue

            if len(section_body) > 1200:
                paras = re.split(r'\n\s*\n', section_body)
                packed = _pack_paragraphs(paras, max_chars=1200)
                for p in packed:
                    chunk_text = f"{doc_title} — {section_title}\n\n{p}"
                    chunks.append(Chunk(
                        text=chunk_text,
                        doc_title=doc_title,
                        section_title=section_title,
                        source_file=source_name,
                        metadata={}
                    ))
            else:
                chunk_text = f"{doc_title} — {section_title}\n\n{section_body}"
                chunks.append(Chunk(
                    text=chunk_text,
                    doc_title=doc_title,
                    section_title=section_title,
                    source_file=source_name,
                    metadata={}
                ))

    else:
        # 3. Document has NO ## headers (e.g. FAQ-style docs with bold questions)
        # Split on blank-line-separated paragraphs
        paragraphs = re.split(r'\n\s*\n', content)

        for p in paragraphs:
            cleaned_p = _clean_markdown_dividers(p.strip())
            if not cleaned_p:
                continue

            # Extract bolded question text if present: e.g. **Question?**
            bold_match = re.search(r'\*\*(.+?)\*\*', cleaned_p)
            if bold_match:
                section_title = bold_match.group(1).strip()
            else:
                section_title = "General"

            if len(cleaned_p) > 1200:
                sub_paras = re.split(r'\n+', cleaned_p)
                packed = _pack_paragraphs(sub_paras, max_chars=1200)
                for sub in packed:
                    chunk_text = f"{doc_title} — {section_title}\n\n{sub}"
                    chunks.append(Chunk(
                        text=chunk_text,
                        doc_title=doc_title,
                        section_title=section_title,
                        source_file=source_name,
                        metadata={}
                    ))
            else:
                chunk_text = f"{doc_title} — {section_title}\n\n{cleaned_p}"
                chunks.append(Chunk(
                    text=chunk_text,
                    doc_title=doc_title,
                    section_title=section_title,
                    source_file=source_name,
                    metadata={}
                ))

    return chunks


def chunk_markdown_file(path: str | Path) -> List[Chunk]:
    """Parse a markdown file from disk into chunks."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Markdown file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    return chunk_markdown_text(text, source_name=file_path.name)


if __name__ == "__main__":
    docs_path = Path("docs")
    if not docs_path.exists():
        docs_path = Path(__file__).parent / "docs"

    print(f"Scanning docs directory: {docs_path.resolve()}")
    total_chunks = 0

    md_files = sorted(docs_path.glob("*.md"))
    if not md_files:
        print("No markdown files found!")
    else:
        print("-" * 60)
        for md_file in md_files:
            file_chunks = chunk_markdown_file(md_file)
            count = len(file_chunks)
            total_chunks += count
            print(f"File: {md_file.name:<30} Chunks: {count:>3}")
            # Show the section titles
            for idx, c in enumerate(file_chunks, 1):
                preview = c.text.replace("\n", " ")[:70]
                print(f"   [{idx}] {c.section_title} -> {preview}...")
            print("-" * 60)

        print(f"Total files: {len(md_files)} | Total chunks created: {total_chunks}")
