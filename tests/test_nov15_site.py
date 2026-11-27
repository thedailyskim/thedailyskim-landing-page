"""November 15 approved edition, exact editorial/design preservation and current archive."""
from pathlib import Path
from bs4 import BeautifulSoup as BS
import hashlib,json,re,unittest
ROOT=Path(__file__).resolve().parents[1]
E=json.loads((ROOT/'tests/nov15_expected.json').read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
def doc(p):return BS((ROOT/p).read_text(),'html.parser')
class November15(unittest.TestCase):
 def test_approved_editorial_style_script_header_locks(self):
  d=doc('editions/2026-11-15.html')
  for sel,expected in E['locks'].items():self.assertEqual([sha(str(x).encode()) for x in d.select(sel)],expected,sel)
  self.assertEqual(len(d.select('article.story')),4);self.assertEqual(len(d.select('p.brief')),24)
 def test_old_site_preserved_except_home_and_previous_navigation(self):
  for rel,expected in E['old_files'].items():
   if rel=='index.html':continue
   raw=(ROOT/rel).read_bytes()
   if rel=='editions/2026-11-14.html':raw=raw.replace('<a href="2026-11-15.html">Sun, Nov 15 →</a></nav>'.encode(),b'<span>Latest edition</span></nav>')
   self.assertEqual(sha(raw),expected,rel)
 def test_complete_archive_and_lead_photo(self):
  raw=(ROOT/'index.html').read_text();rows=json.loads(re.search(r'const SITE_CONFIG = (\{.*?\});',raw,re.S)[1])['editions']
  self.assertEqual(rows[12:],E['old_rows']);self.assertEqual([r['url'] for r in rows],[f'editions/2026-11-{i:02}.html' for i in [27,26,25,24,23,22,21,20,19]+list(range(17,0,-1))])
  d=doc('editions/2026-11-15.html');self.assertEqual(rows[11]['image'],E['lead_photo']);self.assertEqual(d.select_one('meta[property="og:image"]')['content'],E['lead_photo'])
  self.assertEqual([a['href'] for a in d.select('.ds-more-grid a')],[f'2026-11-{i}.html' for i in (14,13,12)])
 def test_exact_reader_targets(self):
  d=doc('editions/2026-11-15.html');self.assertEqual(d.select_one('link[rel=canonical]')['href'],'https://thedailyskim.com/editions/2026-11-15.html')
  self.assertEqual(d.select_one('#tri')['data-answer'],'2')
  self.assertEqual([a['href'] for a in d.select('.poll a')],[f'../email/thanks.html?poll=nov15-2026-school-vaccine-exemptions&vote={v}' for v in ('yes','no')])
  self.assertEqual(d.select_one('.ednav a')['href'],'2026-11-14.html');self.assertEqual(d.select('.ednav a')[-1]['href'],'2026-11-16.html')
