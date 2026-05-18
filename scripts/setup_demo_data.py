"""Run this once to generate demo CSVs: python scripts/setup_demo_data.py"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.demo.sample_datasets import save_demo_csvs

save_demo_csvs()
