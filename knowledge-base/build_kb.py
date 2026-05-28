"""
Build the LanceDB knowledge base from chunks.json.

Reads the parsed chunks, embeds them with all-MiniLM-L6-v2,
and loads them into a LanceDB table for retrieval.

Usage:
    python build_kb.py
    python build_kb.py --chunks chunks.json --db-path ./lancedb

Output: knowledge-base/lancedb/ directory with the 'clinical_patterns' table.
"""

import json
import sys
import argparse
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import lancedb
from sentence_transformers import SentenceTransformer


def load_chunks(chunks_path: Path) -> list[dict]:
    """Load chunks from JSON file."""
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks from {chunks_path}")
    return chunks


def embed_chunks(chunks: list[dict], model_name: str = "all-MiniLM-L6-v2") -> list[dict]:
    """Embed all chunks and add vector field."""
    print(f"Loading embedding model: {model_name}...")
    model = SentenceTransformer(model_name)

    texts = [chunk["text"] for chunk in chunks]
    print(f"Embedding {len(texts)} chunks...")
    vectors = model.encode(texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True)

    for chunk, vector in zip(chunks, vectors):
        chunk["vector"] = vector.tolist()

    print(f"Embedding complete. Vector dimension: {vectors.shape[1]}")
    return chunks


def prepare_for_lancedb(chunks: list[dict]) -> list[dict]:
    """
    Prepare chunks for LanceDB insertion.
    Flatten complex fields for storage.
    """
    records = []
    for chunk in chunks:
        record = {
            "chunk_id": chunk["chunk_id"],
            "source": chunk["source"],
            "chapter": chunk["chapter"],
            "section_title": chunk["section_title"],
            "text": chunk["text"],
            "vector": chunk["vector"],
            "word_count": chunk["word_count"],
            # Flatten lists to strings for LanceDB filtering
            "organ_system": json.dumps(chunk.get("organ_system", [])),
            "biomarkers_mentioned": json.dumps(chunk.get("biomarkers_mentioned", [])),
            # Also store as a searchable text field
            "organ_system_text": " ".join(chunk.get("organ_system", [])),
            "biomarkers_text": " ".join(chunk.get("biomarkers_mentioned", [])),
        }
        records.append(record)
    return records


def build_database(records: list[dict], db_path: Path):
    """Create or overwrite the LanceDB table."""
    print(f"Connecting to LanceDB at: {db_path}")
    db = lancedb.connect(str(db_path))

    # Drop existing table if it exists
    try:
        db.drop_table("clinical_patterns")
        print("Dropped existing 'clinical_patterns' table.")
    except Exception:
        pass

    # Create new table
    table = db.create_table("clinical_patterns", data=records)
    print(f"Created table 'clinical_patterns' with {len(records)} records.")

    # Create full-text search index on biomarkers text
    try:
        table.create_fts_index("biomarkers_text")
        print("Created FTS index on 'biomarkers_text'.")
    except Exception as e:
        print(f"FTS index creation failed (non-critical): {e}")

    # Verify
    sample = table.search(records[0]["vector"]).limit(3).to_list()
    print(f"Verification: search returned {len(sample)} results.")
    if sample:
        print(f"  Top result: {sample[0].get('section_title', 'N/A')}")

    return table


def print_stats(chunks: list[dict]):
    """Print knowledge base statistics."""
    print("\n" + "=" * 60)
    print("KNOWLEDGE BASE STATISTICS")
    print("=" * 60)

    # Organ system distribution
    system_counts: dict[str, int] = {}
    for chunk in chunks:
        for system in chunk.get("organ_system", []):
            system_counts[system] = system_counts.get(system, 0) + 1

    print("\nOrgan system coverage:")
    for system, count in sorted(system_counts.items(), key=lambda x: -x[1]):
        print(f"  {system}: {count} chunks")

    # Word count stats
    word_counts = [c["word_count"] for c in chunks]
    print(f"\nChunk sizes:")
    print(f"  Min: {min(word_counts)} words")
    print(f"  Max: {max(word_counts)} words")
    print(f"  Avg: {sum(word_counts) / len(word_counts):.0f} words")
    print(f"  Total: {sum(word_counts)} words")

    # Biomarker coverage
    all_biomarkers = set()
    for chunk in chunks:
        all_biomarkers.update(chunk.get("biomarkers_mentioned", []))
    print(f"\nUnique biomarkers mentioned: {len(all_biomarkers)}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Build LanceDB knowledge base from chunks.json")
    parser.add_argument("--chunks", type=str, default=None,
                        help="Path to chunks.json (default: knowledge-base/chunks.json)")
    parser.add_argument("--db-path", type=str, default=None,
                        help="Path for LanceDB output (default: knowledge-base/lancedb)")
    args = parser.parse_args()

    kb_dir = Path(__file__).parent
    chunks_path = Path(args.chunks) if args.chunks else kb_dir / "chunks.json"
    db_path = Path(args.db_path) if args.db_path else kb_dir / "lancedb"

    if not chunks_path.exists():
        print(f"ERROR: {chunks_path} not found.")
        print("Run parse_wallach.py first to generate chunks.json.")
        print("Usage: python parse_wallach.py raw/chapter2.html raw/chapter3.html ...")
        sys.exit(1)

    # Load
    chunks = load_chunks(chunks_path)
    if not chunks:
        print("ERROR: No chunks found in file.")
        sys.exit(1)

    # Stats
    print_stats(chunks)

    # Embed
    chunks = embed_chunks(chunks)

    # Prepare records
    records = prepare_for_lancedb(chunks)

    # Build DB
    build_database(records, db_path)

    print(f"\nDone! Knowledge base ready at: {db_path}")
    print("You can now run the RAG pipeline.")


if __name__ == "__main__":
    main()
