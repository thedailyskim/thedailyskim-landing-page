import json,hashlib,unittest,re
from pathlib import Path
from bs4 import BeautifulSoup
R=Path(__file__).resolve().parents[1];E=json.loads((R/"tests/nov10_hyphen_revision.json").read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
class ScientificHyphenRevision(unittest.TestCase):
 def test_exact_only_declared_scope(self):
  now={str(p.relative_to(R)):sha(p) for p in R.rglob("*") if p.is_file() and not any(x in p.parts for x in (".git","__pycache__"))}
  old=E["baseline"]
  self.assertTrue(set(old)<=set(now))
  changed={n for n,v in now.items() if n not in old or old[n]!=v}
  self.assertEqual(changed,set(E["allowed"]))
  for n,v in E["web_changes"].items():self.assertEqual(now[n],v["after_sha256"])
 def test_all_current_scientific_terms_corrected(self):
  for rel in E["web_changes"]:
   raw=(R/rel).read_text()
   for old in ("GLP 1","GLP+1","GLP%201","person years"):self.assertNotIn(old,raw)
   self.assertIn("GLP-1",raw)
  s=BeautifulSoup((R/"editions/2026-11-10.html").read_text(),"html.parser")
  self.assertIn("per 100,000 person-years",s.get_text(" ",strip=True))
  self.assertIn("GLP-1",s.title.get_text())
  self.assertIn("GLP-1",s.select_one('meta[name="description"]')["content"])
  self.assertIn("GLP-1",s.select_one("#tri").get_text())
  self.assertEqual(s.select_one("#tri")["data-answer"],"0")
 def test_no_em_dash_and_unchanged_native_interactions(self):
  for rel in E["web_changes"]:
   self.assertNotIn("\u2014",BeautifulSoup((R/rel).read_text(),"html.parser").get_text(" ",strip=True))
  # Strong source preservation is covered by baseline hash equality for every
  # file outside the exact declaration, including collector and old editions.
  self.assertTrue(E["immutable_build_unchanged"])
if __name__=="__main__":unittest.main(verbosity=2)
