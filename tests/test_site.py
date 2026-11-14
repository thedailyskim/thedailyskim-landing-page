"""Offline regression checks. Never submits signup forms or poll requests."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, unquote
import json, re, subprocess, unittest

ROOT = Path(__file__).resolve().parents[1]

class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.tags = []; self.feed(text)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

def text(path):
    return (ROOT/path).read_text()

class SiteChecks(unittest.TestCase):
    def test_internal_links_and_assets(self):
        errors = []
        docs = {p: Document(p.read_text()) for p in ROOT.rglob('*.html')}
        for p, doc in docs.items():
            for tag, attrs in doc.tags:
                for key in ['href', 'src']:
                    raw = attrs.get(key, '')
                    if not raw: continue
                    # AWeber expands its unsubscribe token at email delivery.
                    if p.parent.name == 'email' and raw == '{!remove_web}': continue
                    u = urlsplit(urljoin('https://thedailyskim.com/'+p.relative_to(ROOT).as_posix(), raw))
                    if u.scheme not in ['http','https'] or u.netloc != 'thedailyskim.com': continue
                    target = ROOT/unquote(u.path).lstrip('/')
                    if target.is_dir(): target /= 'index.html'
                    if not target.exists(): errors.append((str(p.relative_to(ROOT)),raw,'missing file')); continue
                    if u.fragment and target in docs:
                        ids = [a.get('id') for _,a in docs[target].tags]
                        if unquote(u.fragment) not in ids: errors.append((str(p.relative_to(ROOT)),raw,'missing anchor'))
        self.assertEqual(errors, [])

    def test_dated_navigation(self):
        home = text('index.html'); new = text('editions/2026-11-06.html')
        config = json.loads(re.search(r'const SITE_CONFIG = (\{.*?\});',home,re.S)[1])
        self.assertEqual([e['url'] for e in config['editions']],[
            'editions/2026-11-14.html','editions/2026-11-13.html','editions/2026-11-12.html','editions/2026-11-11.html','editions/2026-11-10.html','editions/2026-11-09.html','editions/2026-11-08.html','editions/2026-11-07.html','editions/2026-11-06.html','editions/2026-11-05.html','editions/2026-11-04.html','editions/2026-11-03.html',
            'editions/2026-11-02.html','editions/2026-11-01.html'])
        self.assertEqual(len(re.findall(r'class="sw-item[^"]*" href="editions/2026-11-14.html#',home)),5)
        self.assertIn('href="2026-11-06.html">Fri, Nov 6',text('editions/2026-11-05.html'))
        self.assertIn('href="2026-11-05.html">&larr; Thu, Nov 5',new)
        self.assertIn('https://thedailyskim.com/editions/2026-11-06.html',new)
        self.assertIn('Friday, November 6, 2026',new)
        self.assertIn('href="2026-11-05.html"',re.search(r'<section[^>]*class="ds-more".*?</section>',new,re.S)[0])

    def test_locked_chrome_and_scripts(self):
        old = text('editions/2026-11-05.html'); new = text('editions/2026-11-06.html')
        for tag in ['style','script','header']:
            self.assertEqual(re.findall(fr'<{tag}\b.*?</{tag}>',old,re.S),
                             re.findall(fr'<{tag}\b.*?</{tag}>',new,re.S))
        footer = re.search(r'<footer.*?</footer>',old,re.S)[0]
        self.assertEqual(footer.replace('2026-11-05.html','2026-11-06.html'),
                         re.search(r'<footer.*?</footer>',new,re.S)[0])

    def test_signup_configuration_without_submission(self):
        count=0
        for p in [ROOT/'index.html',*sorted((ROOT/'editions').glob('*.html'))]:
            doc=Document(p.read_text())
            forms=[a for t,a in doc.tags if t=='form']
            for a in forms:
                count+=1
                self.assertEqual(a.get('method'),'post')
                self.assertEqual(a.get('action'),'https://www.aweber.com/scripts/addlead.pl')
            if forms:
                vals={a.get('name'):a.get('value') for t,a in doc.tags if t=='input' and a.get('type')=='hidden'}
                self.assertEqual(vals['listname'],'awlist6982848')
                self.assertEqual(vals['redirect'],'https://thedailyskim.com/thanks.html')
                self.assertEqual(vals['meta_redirect_onlist'],'https://thedailyskim.com/thanks.html?already=1')
        self.assertEqual(count,16)

    def test_javascript_syntax_and_trivia_runtime(self):
        cases=0
        for p in ROOT.rglob('*.html'):
            scripts=re.findall(r'<script\b[^>]*>(.*?)</script>',p.read_text(),re.S)
            for script in scripts:
                subprocess.run(['node','--check'],input=script,text=True,check=True,capture_output=True)
                if "function pick(i)" not in script: continue
                answer=int(re.search(r'data-answer="(\d)"',p.read_text())[1])
                for pick in ['A','B','C','D','a','','X']:
                    harness=r"""
const assert=require('node:assert/strict');
function classes(){const s=new Set();return {contains:x=>s.has(x),add:x=>s.add(x)};}
let verdict={textContent:''},scrolls=0;
let buttons=Array.from({length:4},()=>({disabled:false,classList:classes(),addEventListener(n,f){this.click=f;}}));
let q={classList:classes(),getAttribute(){return ANSWER;},querySelectorAll(){return buttons;},querySelector(){return verdict;},scrollIntoView(){scrolls++;}};
let document={getElementById(){return q;}},location={search:SEARCH};
let setTimeout=f=>f();
"""
                    auto=pick.upper() in 'ABCD' and bool(pick)
                    harness=harness.replace('ANSWER',str(answer)).replace('SEARCH',json.dumps('?pick='+pick))
                    harness+=script
                    if auto:
                        i='ABCD'.index(pick.upper())
                        harness+=f"\nassert.equal(verdict.textContent,{json.dumps('You got it.' if i==answer else 'Not quite.')});assert.equal(scrolls,1);"
                    else:
                        harness+="\nassert.equal(q.classList.contains('done'),false);buttons[0].click();"
                    harness+=f"\nassert(q.classList.contains('done'));assert(buttons.every(b=>b.disabled));assert(buttons[{answer}].classList.contains('right'));let before=verdict.textContent;buttons[1].click();assert.equal(verdict.textContent,before);"
                    subprocess.run(['node'],input=harness,text=True,check=True,capture_output=True)
                    cases+=1
        self.assertEqual(cases,98)

if __name__ == '__main__':
    unittest.main(verbosity=2)
