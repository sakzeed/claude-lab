"""claude -p ... --output-format stream-json --verbose | python3 -m labs.trace"""
import sys

from .trace import summarize

for n, step in enumerate(summarize(sys.stdin), 1):
    print(f"{n:>2}. {step.kind:<11} {step.detail}")
