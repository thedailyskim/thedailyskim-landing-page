"""Exact Nov19 inverse; current full-source locks are in test_daily19_site."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
L=json.loads((R/"tests/nov19_maintenance.json").read_text())
def restore_nov19(text,name):
 from nov20_compat import restore_nov20
 text=restore_nov20(text,name)
 for p in reversed(L["pages"].get(name,[])):
  if text.count(p["after"])==1:text=text.replace(p["after"],p["before"],1)
  else:assert text.count(p["before"])==1,(name,"unapproved Nov19 maintenance bytes")
 return text
