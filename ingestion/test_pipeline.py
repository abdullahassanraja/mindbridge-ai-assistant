import sys
from ingest import search, remove_document, ingest_docs_folder, ingest_uploaded_file, get_client, ensure_collection

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("TEST 1: Semantic Search Query 1: 'my partner and I keep arguing'")
print("=" * 70)
results1 = search("my partner and I keep arguing", top_k=3)
for i, res in enumerate(results1, 1):
    print(f"\n[Result {i}] Score: {res['score']:.4f}")
    print(f"Source: {res['source_file']} | Section: {res['section_title']}")
    print(f"Doc Title: {res['doc_title']}")
    print(f"Content:\n{res['text']}")
    print("-" * 50)

print("\n" + "=" * 70)
print("TEST 2: Semantic Search Query 2: 'what happens if I miss my appointment'")
print("=" * 70)
results2 = search("what happens if I miss my appointment", top_k=3)
for i, res in enumerate(results2, 1):
    print(f"\n[Result {i}] Score: {res['score']:.4f}")
    print(f"Source: {res['source_file']} | Section: {res['section_title']}")
    print(f"Doc Title: {res['doc_title']}")
    print(f"Content:\n{res['text']}")
    print("-" * 50)

print("\n" + "=" * 70)
print("TEST 3: Testing remove_document('04_policies.md')")
print("=" * 70)
print("Removing '04_policies.md'...")
remove_document("04_policies.md")

print("\nRe-running Query 2 after removal:")
results2_after = search("what happens if I miss my appointment", top_k=3)
found_removed = any(r['source_file'] == '04_policies.md' for r in results2_after)
print(f"Was '04_policies.md' found in results? {found_removed}")
for i, res in enumerate(results2_after, 1):
    print(f"   [{i}] Score: {res['score']:.4f} | Source: {res['source_file']} | Section: {res['section_title']}")

print("\n" + "=" * 70)
print("TEST 4: Testing ingest_uploaded_file() for future upload path")
print("=" * 70)
sample_upload = """# Special Workshops
## Mindfulness & Stress Reduction Workshop
We offer a 4-week weekend workshop focusing on breathwork, guided meditation, and somatic grounding exercises to tackle chronic workplace burnout.
"""
count = ingest_uploaded_file(sample_upload, filename="uploaded_workshop.md")
print(f"Uploaded file ingested with {count} chunks.")
upload_results = search("somatic breathwork meditation workshop", top_k=2)
print("Search results for workshop query:")
for i, res in enumerate(upload_results, 1):
    print(f"   [{i}] Score: {res['score']:.4f} | Source: {res['source_file']} | Section: {res['section_title']}")

# Clean up uploaded test doc
remove_document("uploaded_workshop.md")

print("\n" + "=" * 70)
print("RE-INGESTING '04_policies.md' TO RESTORE KB TO COMPLETE STATE")
print("=" * 70)
from chunker import chunk_markdown_file
from ingest import _upsert_chunks
client = get_client()
chunks = chunk_markdown_file("docs/04_policies.md")
_upsert_chunks(client, chunks)
print("Knowledge base fully restored with 04_policies.md!")

verify_results = search("what happens if I miss my appointment", top_k=1)
print(f"Verification top result source: {verify_results[0]['source_file']} | Section: {verify_results[0]['section_title']}")
print("=" * 70)
