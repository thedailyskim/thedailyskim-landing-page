"""Exact dated maintenance inverse; never ignores editorial/design changes."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
LEDGER=json.loads((ROOT/"tests/nov16_maintenance.json").read_text())
def restore_nov16(text,name):
 from nov17_compat import restore_nov17
 text=restore_nov17(text,name)
 if (ROOT/"scripts/sync_editions.py").exists():
  sys.path.insert(0,str(ROOT/"scripts"));import sync_editions
  text=sync_editions.shared_latest(text,"editions/2026-11-15.html")
 for pair in reversed(LEDGER["pages"].get(name,[])):
  assert text.count(pair["after"])==1,(name,pair["label"],"unexpected Nov16 maintenance bytes")
  text=text.replace(pair["after"],pair["before"],1)
 return text
