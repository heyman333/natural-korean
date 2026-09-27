"""brunch_urls.txt 의 글을 받아 samples-brunch/ 에 저장한다. 표준 라이브러리만 쓴다.

브런치 글은 작가에게 저작권이 있어서 본문은 저장소에 올리지 않는다(.gitignore).
URL 목록만 올리고, 각자 이 스크립트로 받아서 돌린다.

python3 evals/fetch_brunch.py
"""
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).parent


class Body(HTMLParser):
    """.wrap_body 안의 p·h·blockquote·li 텍스트를 문단 단위로 모은다."""

    def __init__(self):
        super().__init__()
        self.depth = 0  # .wrap_body 안에서의 div 깊이, 0이면 바깥
        self.block = None
        self.paras = []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class") or ""
        if self.depth == 0 and tag == "div" and "wrap_body" in cls.split():
            self.depth = 1
        elif self.depth and tag == "div":
            self.depth += 1
        elif self.depth and tag in ("p", "h2", "h3", "h4", "blockquote", "li"):
            self.block = []
        elif self.block is not None and tag == "br":
            self.block.append(" ")

    def handle_endtag(self, tag):
        if self.depth and tag == "div":
            self.depth -= 1
        elif self.block is not None and tag in ("p", "h2", "h3", "h4", "blockquote", "li"):
            text = re.sub(r"\s+", " ", "".join(self.block)).strip()
            if text:
                self.paras.append(text)
            self.block = None

    def handle_data(self, data):
        if self.block is not None:
            self.block.append(data)


UNITS = "년|월|일|시|분|초|원|만|억|%|개|명|번|살|세|배|주|회|편|권|층|점|위|km|kg|cm"


def facts(text):
    """사실 보존 확인용 앵커: 단위가 붙은 숫자(예: 20년, 4,500원)를 최대 5개."""
    found = re.findall(rf"\d[\d,.]*\s?(?:{UNITS})", text)
    return list(dict.fromkeys(f.strip() for f in found))[:5]


def main():
    out = ROOT / "samples-brunch"
    out.mkdir(exist_ok=True)
    for line in (ROOT / "brunch_urls.txt").read_text().split("\n"):
        if not line.strip() or line.startswith("#"):
            continue
        name, url = line.split(maxsplit=1)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        parser = Body()
        parser.feed(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
        text = "\n\n".join(parser.paras)
        (out / f"{name}.txt").write_text(f"facts: {' | '.join(facts(text))}\n\n{text}\n")
        print(name, len(text), "자")


if __name__ == "__main__":
    main()
