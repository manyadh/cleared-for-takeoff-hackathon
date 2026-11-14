"""All settings come from environment variables so you can flip backends on the board
without touching code. Defaults match the event's reference stack
(github.com/heath0xFF/cleared-for-takeoff-hackathon):

    LFM3-1.7B Q4_0 on the NPU via GenieX v0.10.0  -> http://127.0.0.1:18181
    d1-2B via Transformers on CPU                 -> ~/models/d1-2B
    Audio/Omni via ZETIC wrapper (WAV <=30 s)      -> examples/zetic-lfm/run.py

    MUSTER_MODE=mock      -> everything faked, runs on any laptop (default)
    MUSTER_MODE=device    -> real models on the IQ9
Nothing here ever points at the internet.
"""
import os

MODE = os.getenv("MUSTER_MODE", "mock")

# Text model (LFM3-1.7B on NPU via GenieX) - extraction + reply
LLM_URL = os.getenv("MUSTER_LLM_URL", "http://127.0.0.1:18181/v1")
LLM_MODEL = os.getenv("MUSTER_LLM_MODEL", "LiquidAI/LFM3-1.7B-GGUF:Q4_0")
LLM_COMPUTE = os.getenv("MUSTER_LLM_COMPUTE", "npu")
LLM_JSON_MODE = os.getenv("MUSTER_JSON_MODE", "0") == "1"   # only if the server accepts response_format

# Speech-to-text: mock | zetic
ASR_BACKEND = os.getenv("MUSTER_ASR", "mock")
ZETIC_RUN = os.path.expanduser(os.getenv("MUSTER_ZETIC_RUN", "~/zetic-demo/run.py"))
ZETIC_SDK = os.path.expanduser(os.getenv("MUSTER_ZETIC_SDK", "~/zetic-demo/sdk"))
ZETIC_MODEL = os.path.expanduser(os.getenv("MUSTER_ZETIC_MODEL", "~/zetic-demo/models/lfm3-omni-2b"))

# Triage: rules | d1 | llm
TRIAGE_BACKEND = os.getenv("MUSTER_TRIAGE", "rules")
D1_DIR = os.path.expanduser(os.getenv("MUSTER_D1_DIR", "~/models/d1-2B"))
TRIAGE_THRESHOLD = float(os.getenv("MUSTER_THRESHOLD", "0.5"))   # tune on your demo lines

SITE_ID = os.getenv("MUSTER_SITE", "S07")
DB_PATH = os.getenv("MUSTER_DB", "muster.db")
LOG_PATH = os.getenv("MUSTER_LOG", "muster_log.jsonl")
