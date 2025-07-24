#!/usr/bin/env python3
import json
import sys
import re
import unicodedata
from argparse import ArgumentParser

# MARCODOC = re.compile(r"^msmarco_v2\.1_doc_\d+_\d+#\d+_\d+$")
CLUEWEB_PATTERN = re.compile(r"^clueweb22-en\d{4}-\d{2}-\d{5}:\d+$")
REQUIRED_METADATA_KEYS = {"team_id", "run_id", "run_type"}
ALLOWED_TYPES = {"manual", "automatic", "generation-only"}
RESPONSE_LIMIT = 250 # 400
CITATION_LIMIT = 1000 # 100

def load_topic_ids(path):
    turn_ids = set()
    with open(path, "r", encoding="utf-8") as f:
        try:
            topics = json.load(f)
        except Exception as e:
            print(f"Failed to load JSON file: {e}")
            return turn_ids

        for topic in topics:
            topic_number = topic.get("number")
            for response in topic.get("responses", []):
                turn_id = response.get("turn_id")
                if topic_number is not None and turn_id is not None:
                    full_id = f"{topic_number}_{turn_id}"
                    turn_ids.add(full_id)

    print(f"Loaded {len(turn_ids)} unique turn IDs from topics.")
    return turn_ids

def compute_response_length(entry):
    total = 0
    for a in entry.get("responses", []):
        text = a.get("text", "").strip()
        tokenized = unicodedata.normalize("NFKC", text)
        total += len(tokenized.split())
    return total

def fix_ikat_responses(entry, count, verbose=False):
    current_length = compute_response_length(entry)
    if current_length <= RESPONSE_LIMIT:
        return entry, current_length

    print(f"[Fix-{count}] response_length={current_length} > {RESPONSE_LIMIT}. Trimming responses...")

    responses = entry["responses"]
    while current_length > RESPONSE_LIMIT and responses:
        last = responses.pop()
        text = last["text"].strip()
        tokenized = unicodedata.normalize("NFKC", text)
        length = len(tokenized.split())
        current_length -= length
        if verbose:
            print(f"Removed: {text} ({length} tokens)")
    return entry, current_length

def fix_citations(entry, count, verbose=False):
    """Remove duplicates from references, trim if they exceed the limit, and update indexes accordingly."""
    refs = entry.get("references", [])
    # convert refs to a list from a dict after sorting by value, only keep the keys
    try:
        refs = [k for k, v in sorted(refs.items(), key=lambda item: item[1])]
    except Exception as e:
        # "references must be a dict, with segment IDs as keys and scores as values: {e}")
        print(f"[Fix-{count}] references must be a dict, with segment IDs as keys and scores as values: {e}")
    warnings = []
    
    # Remove duplicates while preserving order
    original_count = len(refs)
    seen = set()
    unique_refs = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            unique_refs.append(ref)
    
    if len(unique_refs) != original_count:
        duplicate_count = original_count - len(unique_refs)
        warning_msg = f"removed {duplicate_count} duplicate reference(s)"
        warnings.append(warning_msg)
        print(f"[Fix-{count}] WARNING: {warning_msg}")
        entry["references"] = unique_refs
        refs = unique_refs
    
    # Trim references if they exceed the limit
    if len(refs) > CITATION_LIMIT:
        print(f"[Fix-{count}] references length={len(refs)} > {CITATION_LIMIT}. Trimming...")
        original_count = len(refs)
        entry["references"] = refs[:CITATION_LIMIT]
        warning_msg = f"references trimmed from {original_count} to {CITATION_LIMIT}"
        warnings.append(warning_msg)
        print(f"[Fix-{count}] WARNING: {warning_msg}")
        
        # Update responses citations for segment IDs
        valid_refs = set(entry["references"])
        for idx, responses in enumerate(entry.get("responses", [])):
            if "citations" in responses:
                old_citations = responses["citations"]
                # Filter out citations that are no longer in references
                new_citations = [c for c in old_citations if c in valid_refs]
                
                if len(new_citations) != len(old_citations):
                    dropped_count = len(old_citations) - len(new_citations)
                    warning_msg = f"responses[{idx}].citations: dropped {dropped_count} citation(s) not found in trimmed references"
                    warnings.append(warning_msg)
                    print(f"[Fix-{count}] WARNING: {warning_msg}")
                    if verbose:
                        dropped_citations = [c for c in old_citations if c not in valid_refs]
                        print(f"Dropped citations: {dropped_citations}")
                
                responses["citations"] = new_citations
    
    return entry, warnings

def validate_entry(entry):
    errors = []
    warnings = []

    md = entry.get("metadata")
    if not isinstance(md, dict):
        errors.append("metadata must be an object")
    else:
        missing = REQUIRED_METADATA_KEYS - md.keys()
        if missing:
            errors.append(f"metadata missing keys: {missing}")
        # else:
        #     turn_id = str(md.get("turn_id", ""))
        #     if turn_id not in valid_topic_ids:
        #         errors.append(f"metadata.turn_id '{turn_id}' not found in topic file")

        if "run_type" in md and md["run_type"] not in ALLOWED_TYPES:
            errors.append(f"invalid metadata.run_type: {md.get('run_type')}")

        if "run_type" not in md:
            warnings.append("field 'run_type' is missing from metadata")

    refs = entry.get("references")
    try:
        # convert refs to a list from a dict after sorting by value, only keep the keys
        refs = [k for k, v in sorted(refs.items(), key=lambda item: item[1])]
    except Exception as e:
        errors.append(f"references must be a dict, with segment IDs as keys and scores as values: {e}")

    if not isinstance(refs, list):
        errors.append("references error in the format")
    else:
        for i, ref in enumerate(refs):
            if not isinstance(ref, str) or not CLUEWEB_PATTERN.match(ref):
                warnings.append(f"reference[{i}] not in CLUEWEB_PATTERN format: {ref}")

    ans = entry.get("responses", [])
    if not isinstance(ans, list):
        errors.append("responses must be a list")
    else:
        for idx, a in enumerate(ans):
            if not isinstance(a, dict):
                errors.append(f"responses[{idx}] must be object")
                continue
            if "text" not in a or not isinstance(a["text"], str):
                errors.append(f"responses[{idx}].text missing or not string")
            if "citations" not in a:
                errors.append(f"responses[{idx}].citations missing")
            if "ptkb_provenance" not in a:
                errors.append(f"responses[{idx}].ptkb_provenance missing")
            else:
                cits = a["citations"]
                try:
                    cits = [k for k, v in sorted(cits.items(), key=lambda item: item[1])]
                except Exception as e:
                    errors.append(f"responses[{idx}].citations must be a dict, with segment IDs as keys and scores as values: {e}")
                    continue
                if not isinstance(cits, list):
                    errors.append(f"responses[{idx}].citations error in the format")

                if not all(isinstance(c, str) for c in cits):
                    errors.append(f"responses[{idx}].citations must be strings (segment IDs)")
                else:
                    for c in cits:
                        if c not in refs:
                            errors.append(f"responses[{idx}].citation not found in references: {c}")

    return errors, warnings

def main():
    p = ArgumentParser(description="Validate and optionally fix TREC iKAT 2025 output format.")
    p.add_argument("--input", help="JSONL input file or '-' for stdin")
    p.add_argument("--topics", required=True, help="Path to TREC iKAT 2025 topic file (JSON)")
    p.add_argument("--fix-length", action="store_true", help=f"Trim responsess to {RESPONSE_LIMIT} tokens if needed", default=True)
    p.add_argument("--fix-citations", action="store_true", help=f"Trim citations to {CITATION_LIMIT} if needed and update indexes", default=True)
    p.add_argument("--verbose", action="store_true", help="Print details when trimming")
    args = p.parse_args()

    valid_topic_ids = load_topic_ids(args.topics)
    input_stream = sys.stdin if args.input == "-" else open(args.input, encoding="utf-8")
    submitted_turn_ids = set()
    
    # Store all entries and track if any fixes were made
    entries_to_write = []
    any_fixes_made = False
    
    total_errors = 0
    total_warnings = 0
    for i, line in enumerate(input_stream, 1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            original_entry = json.loads(json.dumps(entry))  # Deep copy for comparison
            turn_id = entry.get("turn_id")
            if isinstance(turn_id, str):
                submitted_turn_ids.add(turn_id)
        except json.JSONDecodeError as e:
            print(f"[Line {i}] ❌ JSON decode error: {e}")
            total_errors += 1
            continue

        # Apply fixes
        fix_warnings = []
        entry_was_fixed = False
        
        if args.fix_citations:
            entry, citation_warnings = fix_citations(entry, i, verbose=args.verbose)
            fix_warnings.extend(citation_warnings)
            if citation_warnings:
                entry_was_fixed = True

        if args.fix_length:
            original_length = compute_response_length(original_entry)
            entry, current_length = fix_ikat_responses(entry, i, verbose=args.verbose)
            if current_length != original_length:
                entry_was_fixed = True
        else:
            current_length = compute_response_length(entry)

        if entry_was_fixed:
            any_fixes_made = True

        errors, warnings = validate_entry(entry)

        if errors:
            print(f"[Line {i}] ❌ ERRORS:")
            for e in errors:
                print(f"Error: {e}")
            total_errors += 1
        else:
            if args.verbose:
                print(f"[Line {i}] ✅ OK (Length: {current_length} tokens)")

        # Print all warnings (including fix warnings)
        all_warnings = fix_warnings + warnings
        if len(all_warnings) > 0:
            total_warnings += 1
        for w in all_warnings:
            if not w.startswith("responses[") and not w.startswith("references"):  # Don't duplicate fix warnings
                print(f"[Line {i}] WARNING: {w}")

        # Store entry for potential output
        if args.fix_length or args.fix_citations:
            entries_to_write.append(entry)

    # Check for missing turn_ids or too many turn_ids
    missing_turns = valid_topic_ids - submitted_turn_ids
    additional_turns = submitted_turn_ids - valid_topic_ids
    print(missing_turns)
    print(additional_turns)
    if missing_turns:
        total_errors += 1
        print(f"[File] ❌ ERROR:")
        for turn in sorted(missing_turns):
            print(f"Error: Missing turn_id: {turn}")
        print(f"Error: Total missing turn_ids: {len(missing_turns)}")
    if additional_turns:
        total_errors += 1
        print(f"[File] ❌ ERROR:")
        for turn in sorted(additional_turns):
            print(f"Error: Additional turn_id not in topics: {turn}")
        print(f"Error: Total additional turn_ids: {len(additional_turns)}")
    if not missing_turns and not additional_turns:
        print("\n✅ All required turn_ids are present in the submission.")
    # Write output file only if fixes were made
    if any_fixes_made and (args.fix_length or args.fix_citations):
        output_filename = f"{args.input}.fixed" if args.input != "-" else "stdin.fixed"
        print(f"\nFixes were applied. Writing output to: {output_filename}")
        with open(output_filename, "w", encoding="utf-8") as output_stream:
            for entry in entries_to_write:
                output_stream.write(json.dumps(entry) + "\n")
    elif (args.fix_length or args.fix_citations) and not any_fixes_made and args.verbose:
        print("\nNo fixes were needed. Output file not created.")

    if total_errors:
        print(f"\nValidation completed: {total_errors} line(s) with errors.")
        sys.exit(1)
    elif total_warnings:
        print("\nValidation completed: all lines passed (with possible warnings).")
    else:
        print("\nValidation completed: all lines passed.")

if __name__ == "__main__":
    main()