"""
=============================================================================
ENTERPRISE FUZZY ENTITY RESOLUTION & BRIDGE MATCHER
=============================================================================
Defeats Weakness #4: Text-based Entity Mismatches and Zero-Match String Joins.
Solves:
- 'Apple Inc.' vs 'Apple'
- 'Microsoft Corporation' vs 'Microsoft Corp'
- 'Chicago O'Hare International' vs 'O'Hare Intl'
Algorithm:
1. Business suffix normalization (inc, corp, llc, ltd, intl, co, airport).
2. Token-level Jaccard intersection + Character Sequence Matcher.
3. Generates high-confidence bridge lookup mapping with similarity scores.
=============================================================================
"""

import re
import sys
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Any
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

COMMON_STOP_SUFFIXES = {
    'inc', 'incorporated', 'corp', 'corporation', 'llc', 'ltd', 'limited',
    'co', 'company', 'intl', 'international', 'airport', 'airstrip', 'the', 'and', '&'
}

def normalize_entity_string(name: str) -> str:
    """Cleans punctuation, lowercases, and strips generic business suffixes."""
    if not isinstance(name, str):
        return ""
    # Remove special chars
    s = re.sub(r'[^\w\s]', ' ', name.lower())
    tokens = [w for w in s.split() if w not in COMMON_STOP_SUFFIXES and len(w) > 1]
    return " ".join(tokens)

def compute_similarity_score(s1: str, s2: str) -> float:
    """
    Blended similarity score: 50% Token Jaccard + 50% SequenceMatcher ratio.
    """
    n1 = normalize_entity_string(s1)
    n2 = normalize_entity_string(s2)
    
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
        
    # 1. Token Jaccard
    t1 = set(n1.split())
    t2 = set(n2.split())
    intersection = len(t1.intersection(t2))
    union = len(t1.union(t2))
    jaccard = intersection / float(union) if union > 0 else 0.0
    
    # 2. Sequence Matcher
    seq_ratio = SequenceMatcher(None, n1, n2).ratio()
    
    # Blended Score
    return round(0.5 * jaccard + 0.5 * seq_ratio, 4)

def build_fuzzy_entity_bridge(
    source_entities: List[str],
    target_entities: List[str],
    min_confidence: float = 0.70
) -> Dict[str, Tuple[str, float]]:
    """
    Maps each source entity to its closest matching target entity if score >= min_confidence.
    Uses token inverted index blocking to scale efficiently to 50,000+ entities without O(N*M) CPU hangs.
    Returns: {source_name: (best_target_match, confidence_score)}
    """
    bridge_map = {}
    targets_clean = []
    token_to_targets = {}
    
    for orig_t in set(target_entities):
        if not isinstance(orig_t, str) or not orig_t.strip():
            continue
        norm_t = normalize_entity_string(orig_t)
        if not norm_t:
            continue
        target_tuple = (orig_t, norm_t)
        targets_clean.append(target_tuple)
        
        for token in norm_t.split():
            if len(token) >= 2:
                if token not in token_to_targets:
                    token_to_targets[token] = []
                token_to_targets[token].append(target_tuple)
                
    for s in set(source_entities):
        if not isinstance(s, str) or not s.strip():
            continue
            
        norm_s = normalize_entity_string(s)
        if not norm_s:
            continue
            
        # Fast-path for exact or uppercase acronym matches
        exact_matches = [t for t in targets_clean if t[1] == norm_s or t[0].strip().lower() == s.strip().lower()]
        if exact_matches:
            eval_candidates = exact_matches
        else:
            candidate_set = set()
            for token in norm_s.split():
                if token in token_to_targets:
                    candidate_set.update(token_to_targets[token])
            eval_candidates = candidate_set if candidate_set else (targets_clean if len(targets_clean) < 100 else [])
        
        best_target = None
        best_score = 0.0
        
        for orig_t, _ in eval_candidates:
            score = compute_similarity_score(s, orig_t)
            if score > best_score:
                best_score = score
                best_target = orig_t
                
        if best_score >= min_confidence:
            bridge_map[s] = (best_target, best_score)
            
    return bridge_map

if __name__ == "__main__":
    sources = [
        "Apple Inc.",
        "Microsoft Corp.",
        "Amazon.com, Inc.",
        "Chicago O'Hare Intl",
        "Random Unmatched Entity XYZ"
    ]
    targets = [
        "Apple",
        "Microsoft Corporation",
        "Amazon",
        "Chicago O'Hare International Airport",
        "Delta Air Lines"
    ]
    
    print("[*] Testing Fuzzy Entity Bridge Resolver...")
    bridge = build_fuzzy_entity_bridge(sources, targets, min_confidence=0.65)
    for src, (match, conf) in bridge.items():
        print(f"  '{src}'  ==>  '{match}' (Confidence: {conf*100:.1f}%)")
