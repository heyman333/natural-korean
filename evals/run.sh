#!/usr/bin/env bash
# 샘플 5개를 모델별로 두 조건에서 돌린다.
#   skill    : SKILL.md를 시스템 프롬프트에 붙이고 "다음 글을 고쳐줘."
#   baseline : 스킬 없이 "AI 티를 빼고 사람이 쓴 것처럼 고쳐줘."
# 사용법: evals/run.sh [모델 ...]   (기본: opus 5.5. 이 스킬은 Opus 5.5 전용이다)
# 결과: evals/out/{조건}/{모델}/{샘플}.txt → python3 evals/score.py 로 채점
set -euo pipefail
cd "$(dirname "$0")"
models=("$@")
[ ${#models[@]} -eq 0 ] && models=(claude-opus-5-5)

one() {
  local cond=$1 model=$2 sample=$3 prompt
  local out="out/$cond/$model/$(basename "$sample")"
  mkdir -p "$(dirname "$out")"
  local text; text=$(tail -n +3 "$sample")
  if [ "$cond" = skill ]; then
    prompt="다음 글을 고쳐줘."
    claude -p --tools "" --no-session-persistence --model "$model" \
      --append-system-prompt-file ../skills/natural-korean/SKILL.md "$prompt"$'\n\n'"$text" > "$out"
  else
    prompt="이 글에서 AI 티를 빼고 사람이 쓴 것처럼 자연스럽게 고쳐줘. 고친 글만 내놔."
    claude -p --tools "" --no-session-persistence --model "$model" "$prompt"$'\n\n'"$text" > "$out"
  fi
  echo "done $cond $model $(basename "$sample")"
}
export -f one

for m in "${models[@]}"; do for c in skill baseline; do for s in samples/*.txt; do
  echo "$c $m $s"
done; done; done | xargs -P 4 -n 3 bash -c 'one "$@"' _

python3 score.py
