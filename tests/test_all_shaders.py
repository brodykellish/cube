#!/usr/bin/env python3
"""
Automated GLSL Shader Testing Script

Tests all shaders in shaders/ directory for:
- Compilation errors
- Runtime errors (3 second test)
- GLSL 1.20 compatibility issues
"""

import sys
import os
import subprocess
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def find_all_shaders(shaders_dir: Path) -> List[Path]:
    """Find all .glsl files in shaders directory."""
    return sorted(shaders_dir.glob("**/*.glsl"))

def test_shader(shader_path: Path, timeout: int = 3) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Test a single shader for compilation and runtime errors.

    Returns:
        (success, error_type, error_message)
    """
    # Run shader_preview.py with timeout
    cmd = [
        sys.executable,
        "examples/shader_preview.py",
        "--shader", str(shader_path),
        "--width", "64",
        "--height", "64",
        "--scale", "1"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(__file__).parent
        )

        # Check for compilation errors
        if result.returncode != 0:
            stderr = result.stderr.lower()
            stdout = result.stdout.lower()
            combined = stderr + stdout

            # Identify error type
            if "compile" in combined or "shader" in combined:
                return False, "compilation", result.stderr
            elif "permission" in combined:
                return False, "permission", result.stderr
            elif "import" in combined or "module" in combined:
                return False, "import", result.stderr
            else:
                return False, "runtime", result.stderr

        # Process was killed by timeout (normal for successful shaders)
        return True, None, None

    except subprocess.TimeoutExpired:
        # Timeout means shader ran successfully for 3 seconds
        return True, None, None
    except Exception as e:
        return False, "unknown", str(e)

def extract_error_details(error_message: str) -> Dict[str, str]:
    """Extract useful error details from error message."""
    details = {}

    lines = error_message.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Look for common error patterns
        if "error" in line.lower():
            details['error_line'] = line

        # Extract specific issues
        if "undeclared identifier" in line.lower():
            details['issue'] = "undeclared_identifier"
        elif "no matching overloaded function" in line.lower():
            details['issue'] = "function_overload"
        elif "cannot convert" in line.lower():
            details['issue'] = "type_conversion"
        elif "syntax" in line.lower():
            details['issue'] = "syntax"
        elif "texture" in line.lower():
            details['issue'] = "texture_function"

    return details

def main():
    """Main testing routine."""
    print("=" * 80)
    print("GLSL Shader Testing Suite")
    print("=" * 80)
    print()

    # Find all shaders
    shaders_dir = Path(__file__).parent / "shaders"
    shader_files = find_all_shaders(shaders_dir)

    print(f"Found {len(shader_files)} shader files in {shaders_dir}")
    print()

    # Test results
    results = {
        'total': len(shader_files),
        'passed': [],
        'failed': [],
        'error_types': {}
    }

    # Test each shader
    for i, shader_path in enumerate(shader_files, 1):
        shader_name = shader_path.name
        rel_path = shader_path.relative_to(Path(__file__).parent)

        print(f"[{i}/{len(shader_files)}] Testing {shader_name}...", end=" ", flush=True)

        success, error_type, error_msg = test_shader(shader_path)

        if success:
            print("✓ PASS")
            results['passed'].append(str(rel_path))
        else:
            print(f"✗ FAIL ({error_type})")

            # Extract error details
            error_details = extract_error_details(error_msg) if error_msg else {}

            results['failed'].append({
                'path': str(rel_path),
                'error_type': error_type,
                'error_details': error_details,
                'full_error': error_msg[:500] if error_msg else ""  # Truncate long errors
            })

            # Count error types
            if error_type not in results['error_types']:
                results['error_types'][error_type] = 0
            results['error_types'][error_type] += 1

    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total shaders:    {results['total']}")
    print(f"Passed:           {len(results['passed'])} ({len(results['passed'])/results['total']*100:.1f}%)")
    print(f"Failed:           {len(results['failed'])} ({len(results['failed'])/results['total']*100:.1f}%)")
    print()

    if results['error_types']:
        print("Error types:")
        for error_type, count in sorted(results['error_types'].items()):
            print(f"  {error_type}: {count}")
        print()

    # Show failed shaders
    if results['failed']:
        print("Failed shaders:")
        for failure in results['failed']:
            print(f"  - {failure['path']}")
            if failure['error_details'].get('issue'):
                print(f"    Issue: {failure['error_details']['issue']}")
        print()

    # Save results to JSON
    results_file = Path(__file__).parent / "shader_test_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Detailed results saved to: {results_file}")

    return 0 if not results['failed'] else 1

if __name__ == "__main__":
    sys.exit(main())
