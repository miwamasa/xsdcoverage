#!/usr/bin/env python3
"""Check coverage for all pairwise ISO fixed XML files."""

import subprocess
import re
from pathlib import Path

xsd_file = "test/ISO/IEC62474_Schema_X8.21-120240831.xsd"
xml_dir = Path("generated/pairwise_iso_fixed")

results = []

for xml_file in sorted(xml_dir.glob("pairwise_test_*.xml")):
    # Run coverage check
    result = subprocess.run(
        ["python", "exsisting_code/xsd_coverage.py", xsd_file, str(xml_file)],
        capture_output=True,
        text=True
    )

    output = result.stdout + result.stderr

    # Extract coverage percentage
    coverage_match = re.search(r'カバレッジ率:\s+(\d+\.\d+)%', output.split('【総合カバレッジ】')[-1])
    coverage = coverage_match.group(1) if coverage_match else "0.00"

    # Count undefined elements and attributes
    undefined_elem = output.count("XSDで未定義:")

    # Check for truly undefined (not external schema)
    truly_undefined = 0
    if "【警告: XSDで定義されていない要素パス】" in output:
        truly_undefined_section = output.split("【警告: XSDで定義されていない要素パス】")[1]
        truly_undefined = truly_undefined_section.count("⚠️")

    results.append({
        'file': xml_file.name,
        'coverage': float(coverage),
        'undefined_count': undefined_elem,
        'truly_undefined': truly_undefined
    })

# Print results
print("=" * 80)
print("Pairwise ISO Fixed XML Coverage Summary")
print("=" * 80)
print(f"{'File':<30} {'Coverage':>10} {'Undefined':>12} {'Truly Undefined':>18}")
print("-" * 80)

for r in results:
    print(f"{r['file']:<30} {r['coverage']:>9.2f}% {r['undefined_count']:>12} {r['truly_undefined']:>18}")

# Summary statistics
print("-" * 80)
zero_coverage = [r for r in results if r['coverage'] == 0]
with_undefined = [r for r in results if r['truly_undefined'] > 0]

print(f"\nSummary:")
print(f"  Total files: {len(results)}")
print(f"  Files with 0% coverage: {len(zero_coverage)}")
if zero_coverage:
    print(f"    {', '.join([r['file'] for r in zero_coverage])}")
print(f"  Files with truly undefined elements: {len(with_undefined)}")
if with_undefined:
    for r in with_undefined:
        print(f"    {r['file']}: {r['truly_undefined']} undefined")
