"""Shared transcript spelling normalization without inferred actions."""
import re

def percentages(text):
    return re.sub(r'(?<=\d)\s*(?:%|per\s+cent\b|percent\b)', ' percent', text, flags=re.I)
