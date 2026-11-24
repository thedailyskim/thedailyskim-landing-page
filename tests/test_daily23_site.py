"""Exact Nov23 source locks, scoped maintenance, complete inventory and behavior."""
from pathlib import Path
import copy,hashlib,json,re,subprocess,unittest
from urllib.parse import urljoin,urlsplit,unquote,parse_qs
from bs4 import BeautifulSoup as BS
R=Path(__file__).resolve().parents[1]
from nov24_compat import restore_nov24
def frozen_text(name):return restore_nov24((R/name).read_text(),name)
L=json.loads(frozen_text("tests/nov23_maintenance.json"));B=L["brand"]
BRAND={"daily":"thedailyskim","world":"worldskim","ffd":"factsfirstdaily"}[B]
C=json.loads(frozen_text("docs/nov23-2026/approved-content.json"))
SOURCE=frozen_text("docs/nov23-2026/approved-web-source.txt")
NAV={"daily":"nav.ednav","world":"nav.ed-nav","ffd":"nav.nav"}[B]
sha=lambda b:hashlib.sha256(b).hexdigest()
def undo(text,name):
 for p in reversed(L["pages"].get(name,[])):
  assert text.count(p["after"])==1,(name,"unapproved maintenance bytes")
  text=text.replace(p["after"],p["before"],1)
 return text
def config():
 t=frozen_text("index.html");m=re.search(r"(?:const SITE_CONFIG\s*=\s*|var SITE_CONFIG=)(\{.*?\});",t,re.S)
 return json.loads(subprocess.check_output(["node","-e","process.stdout.write(JSON.stringify(("+m[1]+")))"],text=True))
class November23(unittest.TestCase):
 def test_exact_source_editorial_design_native_protocol(self):
  self.assertEqual(sha(SOURCE.encode()),L["source_sha256"])
  a=BS(SOURCE,"html.parser");b=BS(frozen_text("editions/2026-11-23.html"),"html.parser")
  for sel in ("article.story","#briefing","#deep-dive","#tri","#reader-poll",".poll","style","script","header","form"):
   self.assertEqual([str(x)for x in a.select(sel)],[str(x)for x in b.select(sel)],sel)
  for sel in (NAV,)+(("."+("ds-more-grid"if B=="daily"else"more-grid"),)if B!="ffd"else()):
   b.select_one(sel).replace_with(copy.deepcopy(a.select_one(sel)))
  b.select_one('meta[property="og:image"]')["content"]=a.select_one('meta[property="og:image"]')["content"]
  for x,y in zip(a.select("footer a[href]"),b.select("footer a[href]")):
   if x.get_text()in("Latest edition","Today's edition","Daily trivia","Today's trivia"):y["href"]=x["href"]
  self.assertEqual(str(a),str(b))
 def test_exact_old_site_preservation_and_mutation_rejection(self):
  for name,expected in L["base_hashes"].items():
   if name.startswith("tests/"):continue
   data=frozen_text(name).encode() if name.endswith(".html") else (R/name).read_bytes()
   if name.endswith(".html"):data=undo(data.decode(),name).encode()
   self.assertEqual(sha(data),expected,name)
  for name in L["pages"]:
   raw=frozen_text(name).replace("<title>","<title>UNREVIEWED ",1)
   try:restored=undo(raw,name)
   except AssertionError:continue
   self.assertNotEqual(sha(restored.encode()),L["base_hashes"][name])
  old=BS(undo(frozen_text("index.html"),"index.html"),"html.parser")
  new=BS(frozen_text("index.html"),"html.parser")
  for sel in ("style","header","form"):
   self.assertEqual([str(x)for x in old.select(sel)],[str(x)for x in new.select(sel)],sel)
 def test_complete_inventory_previous_cards_actual_lead(self):
  rows=config()["editions"];urls=[x["url"].split("/")[-1]for x in rows]
  self.assertEqual(urls,["2026-11-23.html","2026-11-22.html","2026-11-21.html","2026-11-20.html","2026-11-19.html"]+[f"2026-11-{n:02}.html"for n in range(17,0,-1)])
  self.assertEqual(rows[1:],json.loads(frozen_text("docs/nov23-2026/old-rows.json")))
  self.assertEqual(rows[0]["image"],L["lead_photo"])
  d=BS(frozen_text("editions/2026-11-23.html"),"html.parser")
  self.assertEqual(d.select_one('meta[property="og:image"]')["content"],L["lead_photo"])
  self.assertEqual(d.select_one("article.story img")["src"],L["lead_photo"])
  self.assertEqual(d.select_one(NAV+" a")["href"],"2026-11-22.html")
  self.assertEqual([(x.get_text(),x["href"])for x in d.select("footer a[href]")if x.get_text()in("Today\'s edition","Daily trivia")],[("Today\'s edition","../editions/2026-11-23.html"),("Daily trivia","../editions/2026-11-23.html#tri")])
  prev=BS(frozen_text("editions/2026-11-22.html"),"html.parser")
  self.assertIsNotNone(prev.select_one(NAV).find("a",href="2026-11-23.html"))
  if B!="ffd":
   cards=d.select(".ds-more-grid a"if B=="daily"else".more-grid a:not(.all)")
   self.assertEqual([x["href"]for x in cards],[f"2026-11-{n}.html"for n in ((22,21,20)if B=="daily"else(18,17))])
   for x in cards:
    past=BS((R/"editions"/x["href"]).read_text(),"html.parser")
    self.assertEqual(x.img["src"],past.select_one("article.story img")["src"])
 def test_poll_trivia_current_headline_binding(self):
  d=BS(frozen_text("editions/2026-11-23.html"),"html.parser")
  self.assertEqual(d.select_one("#tri")["data-answer"],str("ABCD".index(C["trivia"]["correct_letter"])))
  poll=d.select_one(".poll"if B!="world"else"#reader-poll")
  self.assertIn(C["poll"]["question"],poll.get_text(" ",strip=True))
  for a in poll.select("a[href]"):
   q=parse_qs(urlsplit(a["href"]).query);self.assertEqual(q["poll"],[C["poll"]["slug"]]);self.assertIn(q["vote"][0],("yes","no"))
  h=BS(frozen_text("index.html"),"html.parser")
  if B=="daily":self.assertEqual([x.get_text()for x in h.select(".sw-item")],[x["title"]for x in C["stories"]+[C["deep_dive"]]])
  elif B=="world":self.assertEqual(json.loads(h.select_one(".switcher")["data-items"]),[[s["title"],f"editions/2026-11-23.html#s{i+1}"]for i,s in enumerate(C["stories"])])
 def test_all_current_local_links_and_inline_syntax(self):
  domain=BRAND+".com"
  for name in ("index.html","editions/2026-11-23.html")+ (("archive.html",)if B=="world"else(("editions/index.html",)if B=="ffd"else())):
   d=BS(frozen_text(name),"html.parser")
   for a in d.select("[href],[src]"):
    raw=a.get("href",a.get("src",""));u=urlsplit(urljoin("https://"+domain+"/"+name,raw))
    if u.netloc!=domain or u.scheme not in("http","https"):continue
    p=R/unquote(u.path).lstrip("/")
    if p.is_dir():p/="index.html"
    self.assertTrue(p.is_file(),(name,raw))
    if u.fragment and p.suffix==".html":self.assertIsNotNone(BS(p.read_text(),"html.parser").find(id=unquote(u.fragment)),(name,raw))
   for s in d.select("script:not([src])"):
    a=subprocess.run(["node","--check"],input=s.get_text(),text=True,capture_output=True)
    self.assertEqual(a.returncode,0,(name,a.stderr))
