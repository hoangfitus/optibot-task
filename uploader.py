import openai
import os
import time
import tiktoken
from dotenv import load_dotenv
from typing import Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = openai.OpenAI(api_key=api_key)

# Initialize tiktoken encoding once (expensive operation)
try:
    ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:
    ENCODING = None


def get_existing_vector_store(name: str = "OptiBot Docs"):
    """Find existing vector store by name or create new one."""
    try:
        # List existing vector stores
        vector_stores = client.vector_stores.list()
        for vs in vector_stores.data:
            if vs.name == name:
                print(f"Found existing vector store: {vs.id}")
                return vs
    except Exception as e:
        print(f"Error checking existing vector stores: {e}")

    # Create new vector store if none found
    print(f"Creating new vector store: {name}")
    return client.vector_stores.create(name=name)


def get_existing_files_in_vector_store(vector_store_id: str) -> Dict[str, str]:
    """Get mapping of filename to file_id for existing files in vector store - OPTIMIZED."""
    existing_files = {}
    try:
        # Use batch retrieval with pagination for better performance
        files_in_store = client.vector_stores.files.list(
            vector_store_id=vector_store_id, limit=100  # Get more files per request
        )

        # Batch file details retrieval
        file_ids = [file_obj.id for file_obj in files_in_store.data]

        # Use ThreadPoolExecutor for parallel file detail retrieval
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_id = {
                executor.submit(client.files.retrieve, file_id): file_id
                for file_id in file_ids
            }

            for future in as_completed(future_to_id):
                try:
                    file_details = future.result()
                    if hasattr(file_details, "filename"):
                        existing_files[file_details.filename] = file_details.id
                except Exception as e:
                    print(f"Error retrieving file details: {e}")

    except Exception as e:
        print(f"Error getting existing files: {e}")

    return existing_files


def upload_files_parallel(filepaths: list) -> list:
    """Upload multiple files in parallel for better performance."""
    uploaded_files = []

    def upload_single_file(filepath):
        try:
            with open(filepath, "rb") as f:
                return client.files.create(file=f, purpose="assistants")
        except Exception as e:
            print(f"Error uploading {filepath}: {e}")
            return None

    # Use ThreadPoolExecutor for parallel uploads
    with ThreadPoolExecutor(
        max_workers=3
    ) as executor:  # Conservative limit to avoid rate limits
        future_to_path = {
            executor.submit(upload_single_file, filepath): filepath
            for filepath in filepaths
        }

        for future in as_completed(future_to_path):
            result = future.result()
            if result:
                uploaded_files.append(result)

    return uploaded_files


def upload_files_delta(files_to_upload: Dict, vector_store_id: str) -> Dict:
    """Upload only new and updated files to vector store - OPTIMIZED."""
    upload_counts = {"added": 0, "updated": 0, "total_chunks": 0}

    # Get existing files in vector store (already optimized)
    existing_files = get_existing_files_in_vector_store(vector_store_id)

    all_file_ids = []
    files_to_remove = []

    # Collect all files to upload
    new_files = files_to_upload.get("new", [])
    updated_files = files_to_upload.get("updated", [])
    all_files_to_upload = new_files + updated_files

    if not all_files_to_upload:
        return upload_counts

    # Mark old updated files for removal (batch operation later)
    for filepath in updated_files:
        filename = os.path.basename(filepath)
        if filename in existing_files:
            files_to_remove.append(existing_files[filename])

    # Remove old files in parallel (for updated files)
    if files_to_remove:
        print(f"Removing {len(files_to_remove)} old file versions...")

        def remove_file(file_id):
            try:
                client.vector_stores.files.delete(
                    file_id=file_id, vector_store_id=vector_store_id
                )
            except Exception as e:
                print(f"Warning: Could not remove file {file_id}: {e}")

        with ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(remove_file, files_to_remove))

    # Upload all files in parallel
    print(f"Uploading {len(all_files_to_upload)} files to OpenAI storage...")
    uploaded_files = upload_files_parallel(all_files_to_upload)

    # Collect file IDs and update counts
    for i, uploaded_file in enumerate(uploaded_files):
        if uploaded_file:
            all_file_ids.append(uploaded_file.id)
            if i < len(new_files):
                upload_counts["added"] += 1
            else:
                upload_counts["updated"] += 1

    # Add files to vector store in one batch
    if all_file_ids:
        print(f"Adding {len(all_file_ids)} files to vector store...")
        batch = client.vector_stores.file_batches.create(
            vector_store_id=vector_store_id, file_ids=all_file_ids
        )

        # Optimized status checking with exponential backoff
        wait_time = 1
        max_wait = 30
        while batch.status in ["queued", "in_progress"]:
            time.sleep(wait_time)
            batch = client.vector_stores.file_batches.retrieve(
                vector_store_id=vector_store_id, batch_id=batch.id
            )
            wait_time = min(wait_time * 1.5, max_wait)  # Exponential backoff

        if batch.status == "completed":
            print(f"Successfully processed {len(all_file_ids)} files")
        else:
            print(f"Batch processing failed with status: {batch.status}")

    # Calculate chunk estimates (optimized)
    upload_counts["total_chunks"] = estimate_chunks_for_files(files_to_upload)

    return upload_counts


def estimate_chunks_for_files(files_to_upload: Dict) -> int:
    """Estimate total chunks for uploaded files using tiktoken - OPTIMIZED."""
    if not ENCODING:
        return estimate_chunks_fallback(files_to_upload)

    total_chunks = 0

    def process_file(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Get exact token count
            tokens = ENCODING.encode(content)
            token_count = len(tokens)

            # Calculate chunks based on OpenAI's strategy:
            # - max_chunk_size_tokens: 800
            # - chunk_overlap_tokens: 400
            # - Effective progression: 400 tokens per chunk (after first)
            if token_count <= 800:
                return 1
            else:
                remaining_tokens = token_count - 800
                additional_chunks = (remaining_tokens + 399) // 400  # Ceiling division
                return 1 + additional_chunks

        except Exception:
            return 1  # Fallback

    # Process files in parallel for faster token counting
    all_files = []
    for file_list in files_to_upload.values():
        all_files.extend(file_list)

    if len(all_files) > 5:  # Only use threading for multiple files
        with ThreadPoolExecutor(max_workers=4) as executor:
            chunk_counts = list(executor.map(process_file, all_files))
            total_chunks = sum(chunk_counts)
    else:
        # For few files, sequential processing is faster
        for filepath in all_files:
            total_chunks += process_file(filepath)

    return total_chunks


def estimate_chunks_fallback(files_to_upload: Dict) -> int:
    """Fallback estimation if tiktoken is not available."""
    total_chunks = 0

    for file_list in files_to_upload.values():
        for filepath in file_list:
            try:
                file_size = os.path.getsize(filepath)
                # Updated estimation based on OpenAI's chunking strategy
                estimated_tokens = file_size // 4  # ~4 chars per token
                if estimated_tokens <= 800:
                    chunks = 1
                else:
                    remaining_tokens = estimated_tokens - 800
                    additional_chunks = (remaining_tokens + 399) // 400
                    chunks = 1 + additional_chunks
                total_chunks += chunks
            except Exception:
                total_chunks += 1

    return total_chunks


def upload_and_attach_delta(files_to_upload: Dict, counts: Dict) -> str:
    """
    Upload only changed files to vector store.
    Returns vector store ID.
    """
    # Get or create vector store
    vector_store = get_existing_vector_store("OptiBot Docs")

    # Upload delta files
    upload_counts = upload_files_delta(files_to_upload, vector_store.id)

    # Get final vector store info with actual file counts
    vector_store_info = client.vector_stores.retrieve(vector_store_id=vector_store.id)

    print(f"\n📊 Complete Results:")
    print(f"  Total articles fetched: {counts['total_fetched']}")
    print(f"  Articles added: {upload_counts['added']}")
    print(f"  Articles updated: {upload_counts['updated']}")
    print(f"  Articles skipped: {counts.get('skipped', 0)}")
    print(f"  Total files in vector store: {vector_store_info.file_counts.total}")
    print(f"  Estimated chunks embedded: {upload_counts['total_chunks']}")

    return vector_store.id
