#!/usr/bin/env python3
"""Run the unchanged absolute budget gate against the extracted baseline.
First run measure.py to build that compiler, entirely inside this worktree.
"""
import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('budget', root / 'tests/self-compile-budget.py')
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)
base = root / 'build/cycle-measure/baseline'
budget.COMPILER = base / 'minyarc'
budget.SOURCE = base / 'compiler.min'
budget.OUTPUT = base / 'budget-output.ll'
budget.REFERENCE = base / 'compiler.ll'
budget.main()
