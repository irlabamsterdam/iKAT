<h1>iKAT 2025</h1>

The data for the TREC iKAT 2025 and the scripts are provided in this directory.

<h2>Verification script</h2>

We recommend using this script to verify the output adheres to the expected format. This is our checking script for TREC iKAT 2025. You can see if your submission files conform to it. The script will maintain an errorlog and in the case of some cases also attempt to fix warnings (too long -> we remove sentences from the end, dupe citations -> we remove them, etc.). You’ll get a fixed file if the errors are not major that you can resubmit but please go through all the warnings and error messages to make sure you and the script are doing things as expected!

```bash
python scripts/validate_trec_ikat25.py --input <your-submission-file>.jsonl --topics data/2025_test_topics.json
```

This validation script can be tried with the baseline run provided in <a href="https://github.com/irlabamsterdam/iKAT/blob/main/2025/data/2025_baselines/gpt41mini-bm25-minilm-llama70b-gpt41mini.jsonl">gpt41mini-bm25-minilm-llama70b-gpt41mini.jsonl</a>