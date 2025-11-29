#!/usr/bin/env python3
"""Test a single shader and extract error details."""
import sys
import subprocess
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: test_single_shader.py <shader_path>")
    sys.exit(1)

shader_path = sys.argv[1]
cmd = [
    sys.executable,
    "examples/shader_preview.py",
    "--shader", shader_path,
    "--width", "64",
    "--height", "64",
    "--scale", "1"
]

try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
    if result.returncode != 0:
        # Extract just the error message
        for line in result.stderr.split('\n'):
            if 'Error loading shader:' in line or 'ERROR:' in line:
                print(line)
except subprocess.TimeoutExpired:
    print("PASS: Shader ran successfully")
except Exception as e:
    print(f"Error: {e}")
