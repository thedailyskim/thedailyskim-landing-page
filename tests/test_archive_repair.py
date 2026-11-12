"""Current archive repair regression guards. No live poll/signup requests."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import unittest
from urllib.parse import parse_qs, urljoin, urlsplit, unquote
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
E = json.loads((ROOT / "tests/archive_repair_expected.json").read_text())
NEW = ("2026-11-04", "2026-11-11", "2026-11-12")

def doc(path):
    return BeautifulSoup((ROOT / path).read_text(), "html.parser")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def config():
    return json.loads(re.search(r"const SITE_CONFIG = (\{.*?\});", (ROOT / "index.html").read_text(), re.S)[1])

def without_nav(raw):
    return re.sub(r'<nav\b[^>]*\bclass="ednav"[^>]*>.*?</nav>', "<NAV>", raw, flags=re.S)

class ArchiveRepair(unittest.TestCase):
    def test_all_twelve_dates_accessible_and_no_duplicates(self):
        rows = config()["editions"]
        expected = [f"editions/2026-11-{n:02}.html" for n in range(12, 0, -1)]
        self.assertEqual([x["url"] for x in rows], expected)
        self.assertEqual(len({x["url"] for x in rows}), 12)
        self.assertEqual(len({x["title"] for x in rows}), 12)
        for row in rows:
            self.assertTrue((ROOT / row["url"]).is_file())
        preserved = [row for row in rows if row["url"][9:19] not in NEW]
        self.assertEqual(preserved, E["original_archive"])

    def test_old_editions_and_non_navigation_bytes_unchanged(self):
        for rel, expected in E["original_files"].items():
            if not re.fullmatch(r"editions/\d{4}-\d{2}-\d{2}\.html", rel):
                if rel not in ("index.html",) and not rel.startswith("tests/"):
                    self.assertEqual(sha((ROOT / rel).read_bytes()), expected, rel)
                continue
            if Path(rel).stem in ("2026-11-03", "2026-11-05", "2026-11-10"):
                self.assertEqual(sha(without_nav((ROOT / rel).read_text()).encode()),
                                 E["original_without_nav"][rel], rel)
            else:
                self.assertEqual(sha((ROOT / rel).read_bytes()), expected, rel)

    def test_chrome_signup_collector_and_styles_are_locked(self):
        baseline = E["locked"]
        for day in NEW:
            d = doc(f"editions/{day}.html")
            for selector, hashes in baseline.items():
                self.assertEqual([sha(str(n).encode()) for n in d.select(selector)], hashes, (day, selector))
        home = doc("index.html")
        for selector, hashes in E["home_locked"].items():
            self.assertEqual([sha(str(n).encode()) for n in home.select(selector)], hashes, selector)

    def test_notices_dates_metadata_shares_and_trivia(self):
        for day in NEW:
            data = E["content"][day]
            d = doc(f"editions/{day}.html")
            covered = f"November {int(day[-2:])}, 2026"
            kind = "Archive Edition" if day.endswith("12") else "Retrospective Edition"
            self.assertEqual(d.select_one("[data-archive-notice]").get_text(),
                             f"{kind} · Covers {covered} · Added November 12, 2026.")
            self.assertEqual(len(d.select("[data-reporting-cutoff]")), 1)
            self.assertIn(covered, d.h1.get_text())
            self.assertEqual(d.title.get_text(), data["title"])
            self.assertEqual(d.select_one('link[rel=canonical]')["href"],
                             f"https://thedailyskim.com/editions/{day}.html")
            self.assertEqual(d.select_one('meta[name=description]')["content"], data["description"])
            self.assertEqual(urlsplit(d.select_one('meta[property="og:image"]')["content"]).path,
                             urlsplit(data["stories"][0]["photo"]["image_url"]).path)
            tri = d.select_one("#tri")
            self.assertEqual(tri["data-answer"], str("ABCD".index(data["trivia"]["correct_letter"])))
            self.assertEqual(len(tri.select(".qz-opt")), 4)
            for n in d.select(".share a[href]"):
                flat = " ".join(v for rows in parse_qs(urlsplit(n["href"]).query).values() for v in rows)
                self.assertIn(day + ".html", flat)
                self.assertNotIn("2026-11-10.html", flat)
            self.assertIn("November 12-19, 2026", d.select_one(".poll").get_text())

    def test_complete_content_and_photo_slot_integrity(self):
        seen = set()
        for day in NEW:
            data = E["content"][day]
            d = doc(f"editions/{day}.html")
            stories = d.select("article.story")
            self.assertEqual(len(stories), 4)
            for node, item in zip(stories, data["stories"], strict=True):
                self.assertEqual(node.h3.get_text(), item["title"])
                self.assertEqual(len(node.find_all("p", recursive=False)), 2)
                self.assertGreaterEqual(len(node.select("a[href]")), 2)
                self.assertEqual(node.img["alt"], item["photo"]["alt"])
            for section in ("world-view", "need-to-know", "money-markets", "future-frontiers", "the-score", "life-culture"):
                self.assertEqual(len(d.select(f"#{section} p.brief")), 4)
                self.assertTrue(all(n.select("a[href]") for n in d.select(f"#{section} p.brief")))
            deep = d.select_one("#deep-dive")
            paragraphs = [p for p in deep.find_all("p", recursive=False) if "kicker" not in p.get("class", [])]
            self.assertEqual(len(paragraphs), 4)
            for p, label in zip(paragraphs, ("What happened.", "Why it matters.", "What each side says.", "What comes next.")):
                self.assertTrue(p.get_text().startswith(label))
                self.assertTrue(50 <= len(p.get_text(" ", strip=True).split()) <= 70)
            for n in stories + [deep]:
                image = urlsplit(n.img["src"])
                self.assertEqual(image.hostname, "images.unsplash.com")
                self.assertNotIn(image.path, seen)
                self.assertNotIn(image.path, E["previous_photo_paths"])
                seen.add(image.path)
            prose = " ".join(n.get_text(" ", strip=True) for n in stories + [deep])
            self.assertNotIn("—", prose)

    def test_navigation_and_latest_homepage(self):
        for n in range(1, 13):
            day = f"2026-11-{n:02}"
            nav = doc(f"editions/{day}.html").select_one("nav.ednav")
            self.assertIsNotNone(nav)
            if n in (3, 4, 5, 10, 11, 12):
                if n > 1:
                    self.assertIsNotNone(nav.select_one(f'a[href="2026-11-{n-1:02}.html"]'))
                if n < 12:
                    self.assertIsNotNone(nav.select_one(f'a[href="2026-11-{n+1:02}.html"]'))
        links = doc("index.html").select(".sw-item")
        data = E["content"]["2026-11-12"]
        self.assertEqual([n.get_text() for n in links],
                         [s["title"] for s in data["stories"]] + [data["deep_dive"]["title"]])
        self.assertTrue(all("2026-11-12.html#" in n["href"] for n in links))
        self.assertIn("2026-11-12", config()["editions"][0]["url"])

    def test_all_internal_links_anchors_and_javascript_syntax(self):
        documents = {p.resolve(): BeautifulSoup(p.read_text(), "html.parser") for p in ROOT.rglob("*.html")}
        for p, d in documents.items():
            for n in d.select("[href],[src]"):
                value = n.get("href", n.get("src", ""))
                if value == "{!remove_web}":
                    continue
                u = urlsplit(urljoin("https://thedailyskim.com/" + p.relative_to(ROOT).as_posix(), value))
                if u.hostname != "thedailyskim.com" or u.scheme != "https":
                    continue
                target = ROOT / unquote(u.path).lstrip("/")
                if target.is_dir():
                    target /= "index.html"
                self.assertTrue(target.is_file(), (p.name, value))
                if u.fragment and target.resolve() in documents:
                    self.assertIsNotNone(documents[target.resolve()].find(id=unquote(u.fragment)), (p.name, value))
            for script in d.select("script:not([src])"):
                r = subprocess.run(["node", "--check"], input=script.get_text(), text=True, capture_output=True)
                self.assertEqual(r.returncode, 0, (p.name, r.stderr))

if __name__ == "__main__":
    unittest.main(verbosity=2)
