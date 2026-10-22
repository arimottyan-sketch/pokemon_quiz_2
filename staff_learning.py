"""Pure learning/session assembly logic; DOES NOT author or modify Pokémon facts."""
import csv
import io
import random
from collections import Counter
from datetime import datetime, timezone, timedelta

from quiz_engine import REGIONS, make_questions, supplementary_records

EXTRA_KINDS = {'ゲーム公式HP', 'アニメ公式', 'ゲーム内図鑑の補足', '公式図鑑プロフィール', '公式グッズ紹介'}
ALL_REGION = '両方'
MODE_LABELS = {
    'mix': 'バランスよく（おすすめ）',
    'identification': '姿を見て名前を選ぶ',
    'description': '図鑑説明から名前を選ぶ（画像付き）',
    'picture': '姿から図鑑説明を選ぶ',
    'extra_description': '公式トリビアから名前を選ぶ（画像付き）',
}
DISPLAY_MODES = {v:k for k,v in MODE_LABELS.items()}


def region_for(pid):
    for name, identifiers in REGIONS.items():
        if pid in identifiers:
            return name
    raise ValueError(f'対象外: {pid}')


def pool_ids(db, region, mode):
    regions = REGIONS if region == ALL_REGION else {region: REGIONS[region]}
    pool = [p for ids in regions.values() for p in ids if str(p) in db['pokemon']]
    if mode == 'extra_description':
        pool = [p for p in pool if eligible_extra(db['pokemon'][str(p)])]
    return pool


def eligible_extra(row):
    return [rec for rec in supplementary_records(row) if rec['kind'] in EXTRA_KINDS]


def plan_session(db, region, style, count, *, priority_ids=None, seed=None):
    """Build independent four-choice tasks; the source sentences remain byte-for-byte unchanged.

    priority_ids: restrict to previously missed/bookmarked Pokémon; pools for wrong choices
    remain whole region so even a one-item review can have four choices.
    """
    if style not in MODE_LABELS:
        raise ValueError('不正な出題モード')
    rng = random.Random(seed)
    candidates = pool_ids(db, region, 'extra_description' if style == 'extra_description' else 'description')
    if priority_ids is not None:
        wanted = {str(p) for p in priority_ids}
        candidates = [p for p in candidates if str(p) in wanted]
    rng.shuffle(candidates)
    if count != '全問':
        if not isinstance(count, int) or count < 1:
            raise ValueError('問題数が不正です')
        candidates = candidates[:count]
    if not candidates:
        return []
    selections = []
    modes = ['identification', 'description', 'picture', 'extra_description']
    mode_usage = Counter()
    for pid in candidates:
        if style == 'mix':
            possible = modes if eligible_extra(db['pokemon'][str(pid)]) else modes[:3]
            low = min(mode_usage[m] for m in possible)
            options = [m for m in possible if mode_usage[m] == low]
            mode = rng.choice(options)
        else:
            mode = style
        mode_usage[mode] += 1
        selections.append((pid, mode))
    buckets = {}
    for pid, mode in selections:
        buckets.setdefault((region_for(pid), mode), []).append(pid)
    indexed = {}
    for (one_region, mode), ids in buckets.items():
        questions = make_questions(db, one_region, mode, ids=ids, seed=rng.getrandbits(64))
        for q in questions:
            indexed[str(q['id'])] = q
    # Keep the selected shuffled order so the session cannot leak question order.
    return [indexed[str(pid)] for pid, _ in selections]


def progress_csv(rows, db):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['記録時刻（JST）', '地方', '図鑑番号', 'ポケモン', '問題形式', '正誤'])
    for row in rows:
        pokemon = db['pokemon'][str(row['id'])]
        writer.writerow([row['when'], region_for(row['id']),
                         pokemon.get('national_id', row['id']), pokemon['name'],
                         MODE_LABELS.get(row['mode'],row['mode']), '正解' if row['correct'] else '不正解'])
    return '\ufeff'+output.getvalue()


def make_history(pid, mode, correct):
    return {'id':pid,'mode':mode,'correct':bool(correct),
            'when':datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S %z')}
