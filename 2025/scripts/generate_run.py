#!/usr/bin/env python3
import json
import sys
import os
from argparse import ArgumentParser

def replace_extension(path, new_ext):
    return os.path.splitext(path)[0] + new_ext

def generate_trec_run(submission_path, output_path=None):
    if output_path is None:
        output_path = replace_extension(submission_path, ".run")

    with open(submission_path, "r", encoding="utf-8") as infile, open(output_path, "w", encoding="utf-8") as outfile:
        for line_num, line in enumerate(infile, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                turn_id = entry.get("turn_id")
                references = entry.get("references", {})
                metadata = entry.get("metadata", {})
                run_name = metadata.get("run_id", "default_run")

                if not isinstance(references, dict):
                    raise ValueError("references field must be a dictionary")

                # Sort references by descending score
                sorted_refs = sorted(references.items(), key=lambda x: x[1], reverse=True)

                for rank, (doc_id, score) in enumerate(sorted_refs):
                    outfile.write(f"{turn_id}\tQ0\t{doc_id}\t{rank+1}\t{score:.6f}\t{run_name}\n")

            except Exception as e:
                print(f"[Line {line_num}] Error: {e}", file=sys.stderr)

    print(f"TREC run file written to: {output_path}")

if __name__ == "__main__":
    parser = ArgumentParser(description="Generate TREC run file from iKAT submission (JSONL).")
    parser.add_argument("--submission", required=True, help="Path to validated iKAT JSONL submission file.")
    parser.add_argument("--output", help="Optional path to output TREC run file (default: same name with .run)")
    args = parser.parse_args()

    generate_trec_run(args.submission, args.output)
