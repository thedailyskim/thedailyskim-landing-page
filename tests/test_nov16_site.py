"""Nov16 immutable approved news, bounded integration and full archive checks."""
from pathlib import Path
import json,hashlib,copy,re,sys,unittest
from bs4 import BeautifulSoup as BS
from nov16_compat import restore_nov16,LEDGER
ROOT=Path(__file__).resolve().parents[1]
DAILY=not (ROOT/"scripts").exists()
SOURCE=(ROOT/"docs/nov16-2026/approved-web-source.txt").read_text()
def sha(b):return hashlib.sha256(b).hexdigest()
def config():
 from nov17_compat import restore_nov17
 t=restore_nov17((ROOT/"index.html").read_text(),"index.html")
 return json.loads(re.search(r"(?:const SITE_CONFIG = |var SITE_CONFIG=)(\{.*?\});",t,re.S)[1])
class November16(unittest.TestCase):
 def test_immutable_approved_editorial_and_design(self):
  self.assertEqual(sha(SOURCE.encode()),LEDGER["source_sha256"])
  a=BS(SOURCE,"html.parser");b=BS((ROOT/"editions/2026-11-16.html").read_text(),"html.parser")
  for sel in ("article.story","#briefing","#deep-dive","#tri","#reader-poll",".poll","style","script","header","form"):
   self.assertEqual([str(x)for x in a.select(sel)],[str(x)for x in b.select(sel)],sel)
  for sel in (("nav.ednav",".ds-more-grid") if DAILY else ("nav.ed-nav",".more-grid")):
   b.select_one(sel).replace_with(copy.deepcopy(a.select_one(sel)))
  b.select_one('meta[property="og:image"]')["content"]=a.select_one('meta[property="og:image"]')["content"]
  for x in b.select("footer a[href]"):
   if x.get_text() in ("Today's edition","Daily trivia","Latest edition","Today's trivia"):
    x["href"]=x["href"].replace("2026-11-16","2026-11-15")
  self.assertEqual(str(a),str(b))
 def test_old_site_exact_bounded_preservation(self):
  for name,expected in LEDGER["base_hashes"].items():
   if name.startswith("tests/"):continue
   raw=(ROOT/name).read_bytes()
   if name.endswith(".html"):raw=restore_nov16(raw.decode(),name).encode()
   self.assertEqual(sha(raw),expected,name)
  # Exact inverse rejects a hidden historical title edit.
  name="editions/2026-11-15.html";text=(ROOT/name).read_text()
  self.assertNotEqual(sha(restore_nov16(text.replace("<title>","<title>UNAPPROVED ",1),name).encode()),LEDGER["base_hashes"][name])
 def test_complete_archive_and_approved_lead_binding(self):
  rows=config()["editions"]
  self.assertEqual([x["url"]for x in rows],[f"editions/2026-11-{n:02}.html"for n in range(16,0,-1)])
  self.assertEqual(rows[1:],json.loads((ROOT/"docs/nov16-2026/old-rows.json").read_text()))
  d=BS((ROOT/"editions/2026-11-16.html").read_text(),"html.parser")
  self.assertEqual(rows[0]["image"],LEDGER["lead_photo"])
  self.assertEqual(d.select_one('meta[property="og:image"]')["content"],LEDGER["lead_photo"])
  self.assertEqual(d.select_one("article.story img")["src"],LEDGER["lead_photo"])
  self.assertEqual([x["href"]for x in d.select(".ds-more-grid a" if DAILY else ".more-grid a:not(.all)")],[f"2026-11-{n}.html"for n in ((15,14,13)if DAILY else(15,14))])
 def test_current_and_previous_navigation_and_poll(self):
  domain="thedailyskim.com"if DAILY else"worldskim.com"
  d=BS((ROOT/"editions/2026-11-16.html").read_text(),"html.parser")
  a=BS(SOURCE,"html.parser")
  self.assertEqual(d.select_one('link[rel="canonical"]')["href"],f"https://{domain}/editions/2026-11-16.html")
  self.assertEqual(d.select_one("#tri")["data-answer"],"1"if DAILY else"2")
  nav="nav.ednav"if DAILY else"nav.ed-nav"
  self.assertEqual(d.select_one(nav+" a")["href"],"2026-11-15.html")
  prev=BS((ROOT/"editions/2026-11-15.html").read_text(),"html.parser")
  self.assertEqual(prev.select(nav+" a")[-1]["href"],"2026-11-16.html")
  self.assertEqual([x["href"]for x in d.select(".poll a"if DAILY else"#reader-poll a")],[x["href"]for x in a.select(".poll a"if DAILY else"#reader-poll a")])
 def test_all_local_links_and_source_anchors(self):
  from urllib.parse import urljoin,urlsplit,unquote
  domain="thedailyskim.com"if DAILY else"worldskim.com"
  for p in [ROOT/"index.html",ROOT/"editions/2026-11-16.html"]:
   d=BS(p.read_text(),"html.parser")
   for x in d.select("[href],[src]"):
    raw=x.get("href",x.get("src",""));u=urlsplit(urljoin("https://"+domain+"/"+str(p.relative_to(ROOT)),raw))
    if u.netloc!=domain or u.scheme not in("http","https"):continue
    target=ROOT/unquote(u.path).lstrip("/")
    if target.is_dir():target=target/"index.html"
    self.assertTrue(target.exists(),(p,raw))
    if u.fragment and target.suffix==".html":
     self.assertIsNotNone(BS(target.read_text(),"html.parser").find(id=unquote(u.fragment)),(p,raw))
