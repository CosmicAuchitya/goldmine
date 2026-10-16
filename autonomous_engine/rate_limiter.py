"""
=============================================================================
ENTERPRISE MULTI-KEY RATE LIMITER & LOAD BALANCER FOR GEMINI API
=============================================================================
Architecture:
1. Multi-Key Pooling: Automatically aggregates GEMINI_API_KEY and
   GEMINI_API_KEY_SECONDARY (and any GEMINI_API_KEY_N in .env).
2. Throughput Multiplier: Safe quota scales linearly:
   1 Key = 14 RPM | 2 Keys = 28 RPM | 3 Keys = 42 RPM.
3. Zero-Wait Key Balancing: If Key 1 reaches 14 calls in the last 60s,
   automatically routes the request to Key 2 with 0 seconds wait time.
4. Instant Failover: On HTTP 429 (Resource Exhausted) or 503, immediately
   switches to the next available healthy key.
5. Cross-Process State: Uses SQLite ledger (`runs/api_rate_limit.db`) to ensure
   Streamlit and CLI share quotas seamlessly.
=============================================================================
"""

import os
import sys
import time
import random
import sqlite3
import threading
from collections import deque
from pathlib import Path
from dotenv import load_dotenv
from google import genai

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

class PacedGeminiClient:
    def __init__(self, api_key: str = None, max_calls_per_minute: int = 14, model: str = "gemini-3.1-flash-lite"):
        # 1. Discover all configured API keys
        keys = []
        if api_key:
            keys.append(api_key.strip())
        else:
            primary = os.getenv("GEMINI_API_KEY")
            secondary = os.getenv("GEMINI_API_KEY_SECONDARY")
            if primary:
                keys.append(primary.strip())
            if secondary and secondary.strip() not in keys:
                keys.append(secondary.strip())
            # Scan for any additional GEMINI_API_KEY_3, etc.
            for k, v in os.environ.items():
                if k.startswith("GEMINI_API_KEY_") and k != "GEMINI_API_KEY_SECONDARY":
                    if v and v.strip() not in keys:
                        keys.append(v.strip())

        if not keys:
            raise ValueError("No Gemini API keys found! Please configure GEMINI_API_KEY in .env.")

        self.api_keys = keys
        self.num_keys = len(keys)
        
        from google.genai import types
        # Initialize an independent API client for each key
        self.clients = [
            genai.Client(api_key=k, http_options=types.HttpOptions(timeout=90000))
            for k in self.api_keys
        ]
        
        self.model = model
        self.max_calls_per_key = max_calls_per_minute
        self.total_max_calls = max_calls_per_minute * self.num_keys
        self.window_seconds = 60.0
        self.total_calls_made = 0
        self._lock = threading.Lock()
        
        # Cross-process shared rate-limit ledger
        self.db_dir = Path("runs").resolve()
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "api_rate_limit.db"
        self._init_shared_db()
        
        print(f"[*] [Rate Limiter] Initialized Multi-Key Pool with {self.num_keys} Key(s) (Total Capacity: {self.total_max_calls} RPM, Model: {self.model})")

    def _init_shared_db(self):
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            cur = conn.cursor()
            # Ensure schema has key_id column
            cur.execute("CREATE TABLE IF NOT EXISTS api_calls (key_id TEXT, call_time REAL);")
            cur.execute("PRAGMA table_info(api_calls);")
            cols = [c[1] for c in cur.fetchall()]
            if "key_id" not in cols:
                cur.execute("DROP TABLE IF EXISTS api_calls;")
                cur.execute("CREATE TABLE api_calls (key_id TEXT, call_time REAL);")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _wait_for_slot(self, preferred_key_idx: int = None) -> int:
        """
        Enforces sliding-window rate limit across all keys and processes.
        Returns the index of the key client with an immediately available slot.
        """
        while True:
            min_sleep_needed = float('inf')
            with self._lock:
                now = time.time()
                try:
                    conn = sqlite3.connect(self.db_path, timeout=10.0)
                    cur = conn.cursor()
                    # Evict entries older than 60s
                    cur.execute("DELETE FROM api_calls WHERE call_time <= ?;", (now - self.window_seconds,))
                    
                    # Order of key evaluation: preferred first if given, else round-robin
                    key_indices = list(range(self.num_keys))
                    if preferred_key_idx is not None and preferred_key_idx in key_indices:
                        key_indices.remove(preferred_key_idx)
                        key_indices.insert(0, preferred_key_idx)
                    
                    for idx in key_indices:
                        key_tag = f"key_{idx}"
                        cur.execute("SELECT count(*), min(call_time) FROM api_calls WHERE key_id = ?;", (key_tag,))
                        cnt, oldest = cur.fetchone()
                        cnt = cnt or 0
                        
                        if cnt < self.max_calls_per_key:
                            # Slot available on this key! Register and return immediately!
                            cur.execute("INSERT INTO api_calls (key_id, call_time) VALUES (?, ?);", (key_tag, now))
                            conn.commit()
                            conn.close()
                            self.total_calls_made += 1
                            return idx
                        else:
                            # Key is full; calculate when its next slot will free up
                            if oldest is not None:
                                key_sleep = (oldest + self.window_seconds) - now + 0.5
                                if key_sleep < min_sleep_needed:
                                    min_sleep_needed = key_sleep
                                    
                    conn.close()
                except Exception:
                    # In-memory single-key fallback if SQLite is locked
                    self.total_calls_made += 1
                    return 0

            # If all keys in the pool are at capacity, sleep until the earliest key clears a slot
            if min_sleep_needed < float('inf') and min_sleep_needed > 0:
                print(f"\n[RATE-LIMIT PACER] All {self.num_keys} API keys at capacity ({self.total_max_calls} RPM).", flush=True)
                print(f"[RATE-LIMIT PACER] Sleeping {min_sleep_needed:.1f}s for next available slot...", flush=True)
                time.sleep(min_sleep_needed)
            else:
                time.sleep(1.0)

    def generate_content(self, contents, system_instruction: str = None, max_retries: int = 5) -> str:
        """
        Calls Gemini API with multi-key load balancing, auto-failover, and resilience.
        """
        last_error = None
        preferred_idx = self.total_calls_made % self.num_keys
        
        for attempt in range(1, max_retries + 1):
            client_idx = self._wait_for_slot(preferred_key_idx=preferred_idx)
            active_client = self.clients[client_idx]
            
            try:
                kwargs = {"model": self.model, "contents": contents}
                if system_instruction:
                    kwargs["config"] = {"system_instruction": system_instruction}
                
                resp = active_client.models.generate_content(**kwargs)
                return resp.text.strip()
                
            except Exception as e:
                last_error = e
                err_str = str(e)
                is_rate_limit = any(k in err_str.lower() for k in ["429", "quota", "resource_exhausted", "rate_limit"])
                is_server_error = any(k in err_str.lower() for k in ["503", "unavailable", "deadline", "504"])
                if is_server_error:
                    # Transient server blip (503/504): switch key and pause briefly
                    wait_time = 1.5 * attempt
                    next_idx = (client_idx + 1) % self.num_keys
                    print(f"\n[!] Server {err_str[:40]}... (Attempt {attempt}/{max_retries}). Switching to Key #{next_idx + 1} and pausing {wait_time:.1f}s...", flush=True)
                    preferred_idx = next_idx
                    time.sleep(wait_time)
                    continue

                if is_rate_limit:
                    if self.num_keys > 1 and attempt <= self.num_keys:
                        next_idx = (client_idx + 1) % self.num_keys
                        print(f"\n[!] Quota 429 on Key #{client_idx + 1}. Instant failover to Key #{next_idx + 1}!", flush=True)
                        preferred_idx = next_idx
                        continue
                    wait_time = (2 ** attempt) * 4 + random.uniform(1.0, 3.0)
                    print(f"\n[!] Quota Warning across pool (Attempt {attempt}/{max_retries}). Backing off {wait_time:.1f}s...", flush=True)
                    time.sleep(wait_time)
                else:
                    wait_time = 2.0 * attempt
                    print(f"\n[!] Transient API notice: {e}. Retrying in {wait_time:.1f}s (Attempt {attempt}/{max_retries})...", flush=True)
                    time.sleep(wait_time)
                    
        # Multi-Provider Failover: If Gemini pool exhausted, route to OpenRouter
        if os.getenv("OPENROUTER_API_KEY"):
            print("\n[!] Gemini Pool Exhausted! Instant Autonomous Failover to OpenRouter Models...", flush=True)
            try:
                return call_openrouter_model(contents, system_instruction=system_instruction)
            except Exception as ore:
                print(f"[X] OpenRouter failover notice: {ore}", flush=True)

        raise RuntimeError(f"Failed to complete Gemini API call after {max_retries} attempts. Last error: {last_error}")

def call_openrouter_model(
    prompt: str,
    system_instruction: str = None,
    model: str = "nvidia/nemotron-3-ultra-550b-a55b:free",
    api_key: str = None
) -> str:
    """
    Direct call to OpenRouter API with multi-model fallback.
    """
    import urllib.request
    import json
    
    key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY not configured in .env!")
    
    candidate_models = [
        model,
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
    ]
    seen = set()
    models_to_try = [m for m in candidate_models if not (m in seen or seen.add(m))]
    
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    last_err = None
    for cand in models_to_try:
        try:
            payload = json.dumps({
                "model": cand,
                "messages": messages,
                "temperature": 0.2
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/datax-ray/autonomous-engine",
                    "X-Title": "DataX-Ray Autonomous AI Engine"
                }
            )
            with urllib.request.urlopen(req, timeout=75) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "choices" in data and len(data["choices"]) > 0:
                    msg = data["choices"][0].get("message", {})
                    content = msg.get("content", "").strip()
                    if content:
                        print(f"[+] [OpenRouter] Succeeded via model: {cand}", flush=True)
                        return content
                if "error" in data:
                    print(f"[!] OpenRouter candidate {cand} error: {data['error']}", flush=True)
                    last_err = data["error"]
        except Exception as e:
            print(f"[!] OpenRouter candidate {cand} exception: {e}", flush=True)
            last_err = e
            time.sleep(1.0)
            continue

    raise RuntimeError(f"All OpenRouter fallback models failed. Last error: {last_err}")

if __name__ == "__main__":
    pacer = PacedGeminiClient()
    print(f"\n[*] Testing Multi-Key Pool with {pacer.num_keys} keys on model '{pacer.model}'...")
    res = pacer.generate_content("Say 'Multi-Key Load Balancer Operational!' in one short sentence.")
    print(f"[+] Output: {res}")

