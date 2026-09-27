"""out/{조건}/{모델}/{샘플}.txt 를 채점해 표로 출력한다. 표준 라이브러리만 쓴다.

python3 evals/score.py            # 채점표
python3 evals/score.py --detail   # 샘플별 점수까지
python3 evals/score.py --brunch   # samples-brunch/·out-brunch/ 채점 (fetch_brunch.py 로 먼저 받는다)
"""
import difflib
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# SKILL.md "뺄 것": 출간 작가 100명 글에서 거의 안 나오는 표현
BANNED = re.compile(
    r"여백|온도|여정|스며|진정한|비로소|결코|온전히|라는 점|라기보다|인 셈이다|하는 것이죠"
    r"|흥미롭게도|놀랍게도|재미있는 건|핵심은|중요한 건|중요한 것은|다시 말해|요컨대|정리하면"
    r"|이것이 바로|어떨까요\?|—|\*\*"
)
# SKILL.md "줄일 것": 한 편에 2회까지 허용
REDUCE = ["결국", "아니라", "것이다", "하지만", "그리고", "물론", "우리는",
          "에 대해", "통해", "수 있다", "어쩌면", "솔직히"]
# SKILL.md "Opus 5.5 버릇": 사람(출간 작가 100편)보다 Opus 5.5가 훨씬 많이 쓰는 표현
OPUS_TICS = re.compile(r"아니라|아니다\.|[는은]데[, ]|에 가깝|에 가까운|면 된다|만하다|마주하")
HUMAN_TICS = 1.5  # 출간 작가 100편에서 같은 정규식의 1,000자당 빈도
# SKILL.md "번역투와 구조"의 설명 글 규칙: 문두 연결어 연쇄, 이유 꼬리, 발견담
STRUCT = re.compile(r"(?:^|[.?!]\s+|\n)(?:그런데|그래서|대신|따라서)[ ,]|기 때문[이입]|처음에는|처음엔")
HUMAN_CV = 0.56  # 출간 작가 100편 문장 길이 변동계수 중앙값


def body(text):
    """모델 출력에서 고친 글만 남긴다. 첫 '---' 뒤의 메모와 코드펜스는 버린다."""
    text = re.sub(r"^```\w*\n|\n```\s*$", "", text.strip())
    parts = re.split(r"^\s*---\s*$", text, flags=re.M)
    return (parts[0] if len(parts) > 1 else text).strip()


def sentences(text):
    s = re.split(r"\n|(?<=[.?!…])\s+", text)
    return [x.strip() for x in s if len(x.strip()) > 1 and re.search(r"[가-힣]", x)]


def length_rule(text):
    """SKILL.md 규칙: 3문장 이상 문단마다 15자 이하 문장과 70자 이상 문장이 하나씩. 지킨 문단 비율."""
    paras = [[len(s) for s in sentences(p)] for p in re.split(r"\n\s*\n", text)]
    paras = [L for L in paras if len(L) >= 3]
    ok = [min(L) <= 15 and max(L) >= 70 for L in paras]
    return sum(ok) / len(ok) if ok else None  # 대상 문단이 없으면 평균에서 뺀다


def score(text, facts, original=None):
    lens = [len(s) for s in sentences(text)]
    cv = statistics.pstdev(lens) / statistics.mean(lens) if lens else 0
    return {
        "뺄것": len(BANNED.findall(text)),
        "줄일것초과": sum(max(0, text.count(w) - 2) for w in REDUCE),
        "Opus버릇": len(OPUS_TICS.findall(text)) * 1000 / max(len(text), 1),
        "구조버릇": len(STRUCT.findall(text)) * 1000 / max(len(text), 1),
        "CV": cv,
        "길이규칙": length_rule(text),
        "사실보존": sum(f in text for f in facts) / len(facts) if facts else None,
        # 원문 대비 바뀐 비율. 사람 글 대조군에서는 낮을수록 좋다
        "변경률": 1 - difflib.SequenceMatcher(None, original, text, autojunk=False).ratio() if original else 0.0,
    }


# (열 이름, 점수 키, 서식)
COLUMNS = [
    ("뺄 것 (0이 목표)", "뺄것", "{:.1f}"),
    ("줄일 것 초과 (0이 목표)", "줄일것초과", "{:.1f}"),
    (f"Opus 버릇 /천자 (사람 {HUMAN_TICS})", "Opus버릇", "{:.1f}"),
    ("구조 버릇 /천자", "구조버릇", "{:.1f}"),
    (f"문장 길이 CV (사람 {HUMAN_CV})", "CV", "{:.2f}"),
    ("길이 규칙 지킨 문단", "길이규칙", "{:.0%}"),
    ("사실 보존", "사실보존", "{:.0%}"),
    ("변경률", "변경률", "{:.0%}"),
]


def cells(values):
    return " | ".join("-" if values[k] is None else f.format(values[k]) for _, k, f in COLUMNS)


def row(name, scores):
    avg = {}
    for k in scores[0]:
        vals = [s[k] for s in scores if s[k] is not None]
        avg[k] = statistics.mean(vals) if vals else None
    return f"| {name} | {cells(avg)} | {len(scores)} |"


def load_samples(folder):
    out = {}
    for p in sorted((ROOT / folder).glob("*.txt")):
        head, text = p.read_text().split("\n", 1)
        facts = [f.strip() for f in head.removeprefix("facts:").split("|") if f.strip()]
        out[p.stem] = (facts, text.strip())
    return out


def table(samples, outdir, detail):
    print("| 조건 | " + " | ".join(c for c, _, _ in COLUMNS) + " | 편수 |")
    print("|---" * (len(COLUMNS) + 2) + "|")
    print(row("원문", [score(t, f) for f, t in samples.values()]))
    for d in sorted(outdir.glob("*/*")):
        scored, lines = [], []
        for name, (facts, original) in samples.items():
            p = d / f"{name}.txt"
            if p.exists():
                s = score(body(p.read_text()), facts, original)
                scored.append(s)
                lines.append(f"|   {name} | {cells(s)} | |")
        if scored:
            print(row(f"{d.parent.name} / {d.name}", scored))
            if detail:
                print("\n".join(lines))


def main():
    detail = "--detail" in sys.argv
    if "--brunch" not in sys.argv:
        table(load_samples("samples"), ROOT / "out", detail)
        return
    samples = load_samples("samples-brunch")
    # AI 티 상위(a)와 사람 글 대조군(h)을 따로 본다
    for prefix, label in (("a", "AI 티 상위"), ("h", "사람 글 대조군")):
        print(f"\n**{label}**\n")
        table({k: v for k, v in samples.items() if k.startswith(prefix)}, ROOT / "out-brunch", detail)


if __name__ == "__main__":
    # 자체 점검: 채점 규칙이 깨지면 여기서 멈춘다
    t = score("진정한 여정이었다 — 결국 결국 결국. 짧다.", ["여정"], "진정한 여정이었다")
    assert t["뺄것"] == 3 and t["줄일것초과"] == 1 and t["사실보존"] == 1 and 0 < t["변경률"] < 1, t
    assert score("글", [])["사실보존"] is None
    assert len(STRUCT.findall("처음에는 몰랐다. 그런데 알았다.\n그래서 바꿨다. 바쁘기 때문이다.")) == 4
    assert length_rule("짧다. " + "가" * 70 + ". 보통 길이의 문장이다.") == 1.0
    assert body("고친 글\n\n---\n- 메모") == "고친 글"
    main()
