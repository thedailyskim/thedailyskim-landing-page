"""Exact Nov26 inverse for frozen release snapshots; actual current locks separate."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
L=json.loads((R/"tests/nov26_maintenance.json").read_text())
def restore_nov26(text,name):
 for p in reversed(L["pages"].get(name,[])):
  if text.count(p["after"])==1:text=text.replace(p["after"],p["before"],1)
  else:assert text.count(p["before"])==1,(name,"unapproved Nov26 maintenance bytes")
 return text
