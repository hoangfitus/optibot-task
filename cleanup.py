#!/usr/bin/env python3
"""
Cleanup utility for OpenAI files and vector stores.
Use with caution - these operations are irreversible!
"""

import sys
import openai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = openai.OpenAI(api_key=api_key)


def delete_all_files_from_openai():
    """
    Utility function to delete all files from OpenAI storage.
    Use with caution - this will delete ALL files in your OpenAI account!
    """
    print("⚠️  WARNING: This will delete ALL files from your OpenAI account!")
    confirmation = input("Type 'DELETE ALL' to confirm: ")

    if confirmation != "DELETE ALL":
        print("❌ Operation cancelled")
        return

    try:
        # List all files
        files = client.files.list()
        file_count = len(files.data)

        if file_count == 0:
            print("✅ No files found in OpenAI storage")
            return

        print(f"🗑️  Deleting {file_count} files from OpenAI storage...")

        deleted_count = 0
        for file_obj in files.data:
            try:
                client.files.delete(file_obj.id)
                deleted_count += 1
                print(f"  Deleted: {file_obj.filename} ({file_obj.id})")
            except Exception as e:
                print(f"  Failed to delete {file_obj.filename}: {e}")

        print(f"✅ Successfully deleted {deleted_count}/{file_count} files")

    except Exception as e:
        print(f"❌ Error listing files: {e}")


def delete_vector_store_and_files(vector_store_name: str = "OptiBot Docs"):
    """
    Delete a specific vector store and all its associated files.
    """
    print(
        f"⚠️  WARNING: This will delete the '{vector_store_name}' vector store and all its files!"
    )
    confirmation = input(f"Type 'DELETE {vector_store_name}' to confirm: ")

    if confirmation != f"DELETE {vector_store_name}":
        print("❌ Operation cancelled")
        return

    try:
        # Find the vector store
        vector_stores = client.vector_stores.list()
        target_store = None

        for vs in vector_stores.data:
            if vs.name == vector_store_name:
                target_store = vs
                break

        if not target_store:
            print(f"❌ Vector store '{vector_store_name}' not found")
            return

        print(f"🗑️  Deleting vector store: {target_store.id}")

        # Delete the vector store (this also removes files from it)
        client.vector_stores.delete(target_store.id)

        print(f"✅ Successfully deleted vector store '{vector_store_name}'")

    except Exception as e:
        print(f"❌ Error deleting vector store: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python cleanup.py all          # Delete ALL files from OpenAI")
        print("  python cleanup.py vectorstore  # Delete OptiBot Docs vector store")
        print("  python cleanup.py vectorstore <name>  # Delete specific vector store")
        return

    command = sys.argv[1].lower()

    if command == "all":
        delete_all_files_from_openai()
    elif command == "vectorstore":
        store_name = sys.argv[2] if len(sys.argv) > 2 else "OptiBot Docs"
        delete_vector_store_and_files(store_name)
    else:
        print(f"❌ Unknown command: {command}")
        print("Use 'all' or 'vectorstore'")


if __name__ == "__main__":
    main()
