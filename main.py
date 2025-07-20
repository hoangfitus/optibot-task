#!/usr/bin/env python3
"""
Main script to scrape articles and upload them to OpenAI with delta detection.
"""

import os
import sys
from dotenv import load_dotenv
from scraper import fetch_articles_with_delta
from uploader import upload_and_attach_delta

load_dotenv()


def main():
    print("🚀 Starting delta-enabled article scraping and upload process...")

    try:
        # Fetch articles and detect changes in one call
        files_to_upload, counts = fetch_articles_with_delta()

        if counts["new"] == 0 and counts["updated"] == 0:
            print("✅ No changes detected - all articles are up to date!")
            return

        print("☁️ Uploading changes to OpenAI vector store...")
        vector_store_id = upload_and_attach_delta(files_to_upload, counts)

        print("✅ Process completed successfully!")
        print(f"📍 Vector store ID: {vector_store_id}")

    except Exception as e:
        print(f"❌ Error occurred: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
