"""
Wrapper script to run the Booking.com search pipeline.
"""
import os
import sys

# Dynamic path resolution to import from src
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

from src.pipeline import run_search_pipeline

if __name__ == "__main__":
    run_search_pipeline()
