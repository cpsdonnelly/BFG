#!/usr/bin/env python3
"""Launch BFG:XR Simulator"""
import os
import sys

# Ensure we're running from the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

from src.main import main
main()
