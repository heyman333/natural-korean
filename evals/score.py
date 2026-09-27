"""out/{조건}/{모델}/{샘플}.txt 를 채점해 표로 출력한다. 표준 라이브러리만 쓴다.

python3 evals/score.py            # 채점표
python3 evals/score.py --detail   # 샘플별 점수까지
"""
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


def score(text, facts):
    lens = [len(s) for s in sentences(text)]
    cv = statistics.pstdev(lens) / statistics.mean(lens) if lens else 0
    return {
        "뺄것": len(BANNED.findall(text)),
        "줄일것초과": sum(max(0, text.count(w) - 2) for w in REDUCE),
        "CV": cv,
        "길이규칙": length_rule(text),
        "사실보존": sum(f in text for f in facts) / len(facts),
    }


def load_samples():
    out = {}
    for p in sorted((ROOT / "samples").glob("*.txt")):
        head, text = p.read_text().split("\n", 1)
        out[p.stem] = ([f.strip() for f in head.removeprefix("facts:").split("|")], text.strip())
    return out


def row(name, scores):
    avg = {k: statistics.mean([s[k] for s in scores if s[k] is not None] or [0]) for k in scores[0]}
    return (f"| {name} | {avg['뺄것']:.1f} | {avg['줄일것초과']:.1f} | "
            f"{avg['CV']:.2f} | {avg['길이규칙']*100:.0f}% | {avg['사실보존']*100:.0f}% | {len(scores)} |")


def main():
    samples = load_samples()
    detail = "--detail" in sys.argv
    print(f"| 조건 | 뺄 것 (0이 목표) | 줄일 것 초과 (0이 목표) | 문장 길이 CV (사람 {HUMAN_CV}) | 길이 규칙 지킨 문단 | 사실 보존 | 편수 |")
    print("|---|---|---|---|---|---|---|")
    print(row("원문", [score(t, f) for f, t in samples.values()]))
    for d in sorted((ROOT / "out").glob("*/*")):
        scored, lines = [], []
        for name, (facts, _) in samples.items():
            p = d / f"{name}.txt"
            if p.exists():
                s = score(body(p.read_text()), facts)
                scored.append(s)
                if detail:
                    lines.append(f"|   {name} | {s['뺄것']} | {s['줄일것초과']} | {s['CV']:.2f} | {'-' if s['길이규칙'] is None else f"{s['길이규칙']*100:.0f}%"} | {s['사실보존']*100:.0f}% | |")
        if scored:
            print(row(f"{d.parent.name} / {d.name}", scored))
            for line in lines:
                print(line)


if __name__ == "__main__":
    # 자체 점검: 채점 규칙이 깨지면 여기서 멈춘다
    t = score("진정한 여정이었다 — 결국 결국 결국. 짧다.", ["여정"])
    assert t["뺄것"] == 3 and t["줄일것초과"] == 1 and t["사실보존"] == 1, t
    assert length_rule("짧다. " + "가" * 70 + ". 보통 길이의 문장이다.") == 1.0
    assert body("고친 글\n\n---\n- 메모") == "고친 글"
    main()
