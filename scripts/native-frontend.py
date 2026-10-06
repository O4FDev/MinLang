#!/usr/bin/env python3
"""Compile original Minyar input with the experimental native compiler fork."""
import importlib.util
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('minyar_native_driver', Path(__file__).with_name('native-swift.py'))
driver = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = driver
spec.loader.exec_module(driver)

if __name__ == '__main__':
    driver.main(native=True)
