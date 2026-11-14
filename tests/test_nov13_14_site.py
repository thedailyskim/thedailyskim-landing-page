"""Approved November 13/14 website publication; no network writes."""
from pathlib import Path
from bs4 import BeautifulSoup as BS
import hashlib,json,re,unittest
ROOT=Path(__file__).resolve().parents[1]
E=json.loads((ROOT/'tests/nov13_14_expected.json').read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
def doc(day):return BS((ROOT/f'editions/{day}.html').read_text(),'html.parser')
class DatedRelease(unittest.TestCase):
    def test_complete_approved_source_content_and_design_locks(self):
        for day,locks in E['locks'].items():
            d=doc(day)
            for selector,expected in locks.items():
                self.assertEqual([sha(str(x).encode()) for x in d.select(selector)],expected,(day,selector))
            self.assertEqual(len(d.select('article.story')),4)
            self.assertEqual(len(d.select('p.brief')),24)
            self.assertEqual(len(d.select('#deep-dive')),1)
    def test_old_editions_preserved_except_previous_latest_navigation(self):
        for rel,expected in E['old_files'].items():
            raw=(ROOT/rel).read_bytes()
            if rel.endswith('2026-11-12.html'):
                raw=raw.replace(b'<a href="2026-11-13.html">Fri, Nov 13 \xe2\x86\x92</a></nav>',b'<span>Latest edition</span></nav>')
            self.assertEqual(sha(raw),expected,rel)
    def test_archive_preserves_all_original_rows(self):
        raw=(ROOT/'index.html').read_text()
        rows=json.loads(re.search(r'const SITE_CONFIG = (\{.*?\});',raw,re.S)[1])['editions']
        self.assertEqual(rows[2:],E['original_archive'])
        self.assertEqual([x['url'] for x in rows],[f'editions/2026-11-{n:02}.html' for n in range(14,0,-1)])
        self.assertEqual(len(BS(raw,'html.parser').select('.sw-track a[href^="editions/2026-11-14.html#"]')),5)
    def test_new_navigation_and_recent_cards(self):
        for n in (13,14):
            d=doc(f'2026-11-{n}')
            self.assertEqual([a['href'] for a in d.select('.ds-more-grid a')],[f'2026-11-{x:02}.html' for x in range(n-1,n-4,-1)])
            self.assertEqual(d.select_one('.ednav a')['href'],f'2026-11-{n-1:02}.html')
            self.assertEqual(d.select_one('footer nav a')['href'],'../editions/2026-11-14.html')
        self.assertEqual(doc('2026-11-13').select('.ednav a')[-1]['href'],'2026-11-14.html')
        self.assertEqual(doc('2026-11-12').select('.ednav a')[-1]['href'],'2026-11-13.html')
        self.assertEqual(doc('2026-11-14').select_one('.ednav span').get_text(),'Latest edition')
    def test_exact_canonical_trivia_and_poll_links(self):
        for n,slug,answer in [(13,'microsoft-outage','1'),(14,'air-traffic-control','2')]:
            day=f'2026-11-{n}';d=doc(day)
            self.assertEqual(d.select_one('link[rel=canonical]')['href'],f'https://thedailyskim.com/editions/{day}.html')
            self.assertEqual(d.select_one('#tri')['data-answer'],answer)
            self.assertEqual([a['href'] for a in d.select('.poll a')],[f'../email/thanks.html?poll=nov{n}-2026-{slug}&vote={v}' for v in ('yes','no')])
