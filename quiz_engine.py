"""Quiz and Pokémon information browser. Source texts are kept unchanged."""
import random
import requests

# Bundled quiz functions; no external quiz modules required.
import json
import random
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

PALDEA_FORMS = ('128-paldea-combat', '128-paldea-blaze', '128-paldea-aqua', '194-paldea')

REGIONS = {
    'イッシュ': list(range(494, 650)),
    'パルデア': list(range(906, 1026)) + list(PALDEA_FORMS),
}
APPROVED_HOSTS = {'zukan.pokemon.co.jp', 'www.pokemon.co.jp', 'www.pokemon-card.com', 'www.tv-tokyo.co.jp', 'www.pokemon.jp', 'novel-kimiame.pokemon.co.jp', 'pokemongo.com'}
SOURCE_KINDS = {'ゲーム内図鑑', 'ゲーム公式HP', 'ポケカ公式', 'アニメ公式', '大会公式', '公式図鑑プロフィール', 'ゲーム内図鑑の補足', '公式グッズ紹介', 'ポケモンだいすきクラブ公式記事', '公式小説', '公式短編小説（作中人物の発言）', 'ポケモン公式大会ニュース'}
SENSITIVE_KINDS = {'ポケカ公式', '大会公式'}


def source_is_allowed(rec):
    try:
        p = urlparse(rec['url'])
        if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
            return False
        host = p.hostname
        if host in {'x.com', 'twitter.com'}:
            if rec.get('kind') != 'アニメ公式':
                return False
            account = rec.get('verified_account', '').strip().lower().lstrip('@')
            proof = rec.get('account_proof_url', '')
            proof_host = urlparse(proof).hostname if proof else None
            return bool(account and proof_host in {'www.pokemon.co.jp', 'www.tv-tokyo.co.jp'}
                        and p.path.lower().startswith('/' + account + '/status/'))
        if host not in APPROVED_HOSTS:
            return False
        if rec.get('kind') == 'ポケモン公式大会ニュース':
            return host == 'www.pokemon.co.jp' and p.path.startswith('/ex/pjcs/')
        if host == 'pokemongo.com':
            return rec.get('kind') == 'ゲーム公式HP' and p.path.startswith('/ja/news/')
        if host == 'www.pokemon.jp':
            return rec.get('kind') == 'ポケモンだいすきクラブ公式記事'
        if host == 'novel-kimiame.pokemon.co.jp':
            return rec.get('kind') in {'公式小説','公式短編小説（作中人物の発言）', 'ポケモン公式大会ニュース'}
        if rec.get('kind') in ('ポケカ公式', '大会公式'):
            return host == 'www.pokemon-card.com'
        if rec.get('kind') in ('ゲーム内図鑑', '公式図鑑プロフィール', 'ゲーム内図鑑の補足'):
            return host in {'zukan.pokemon.co.jp', 'www.pokemon.co.jp'}
        if host == 'www.tv-tokyo.co.jp':
            return rec.get('kind') == 'アニメ公式'
        return True
    except (KeyError, ValueError, TypeError):
        return False


def parse_date(s, key):
    if not isinstance(s, str):
        raise ValueError(f'{key} は YYYY-MM-DD 形式の実日付が必須です')
    try:
        result = date.fromisoformat(s)
        if result.isoformat() != s:
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise ValueError(f'{key} は YYYY-MM-DD 形式の実日付が必須です') from None


def three_year_cutoff(today=None):
    today = today or date.today()
    try:
        return today.replace(year=today.year - 3)
    except ValueError:  # leap day: 2/29 -> 2/28
        return today.replace(year=today.year - 3, month=2, day=28)


def is_recent(rec, today=None):
    """Official card species flavor is timeless; card mechanics and events are time-limited."""
    if rec.get('kind') == 'ポケカ公式' and rec.get('card_text_role') == 'species_flavor':
        return bool(rec.get('quiz_approved') is True and rec.get('verified_on')
                    and rec.get('url', '').startswith('https://www.pokemon-card.com/card-search/details.php/card/'))
    if rec.get('kind') not in SENSITIVE_KINDS:
        return True
    key = 'first_release_on' if rec['kind'] == 'ポケカ公式' else 'event_date'
    try:
        d = parse_date(rec[key], key)
    except (ValueError, KeyError):
        return False
    today = today or date.today()
    return three_year_cutoff(today) <= d <= today


def read_db(path=None):
    path = Path(path) if path else Path(__file__).resolve().parent / 'data' / 'official_quotes.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    validate_db(data)
    return data


def validate_db(data):
    if data.get('schema_version') != 1 or not isinstance(data.get('pokemon'), dict):
        raise ValueError('問題データ形式が不正です')
    for key, item in data['pokemon'].items():
        if key in PALDEA_FORMS:
            pid = key
            if item.get('national_id') not in (128, 194) or not item.get('pokeapi_slug'):
                raise ValueError(f'リージョンフォームの情報不足: {key}')
        else:
            try:
                pid = int(key)
            except ValueError:
                raise ValueError(f'番号キーが不正: {key}') from None
            if str(pid) != key:
                raise ValueError(f'番号キーが不正: {key}')
        if not any(pid in ids for ids in REGIONS.values()):
            raise ValueError(f'対象外の番号: {key}')
        if item.get('id') != pid or not item.get('name'):
            raise ValueError(f'図鑑番号と名前の不整合: {pid}')
        quotes = item.get('quotes')
        if not isinstance(quotes, list) or not quotes:
            raise ValueError(f'公式原文が未登録: {pid}')
        if not any(rec.get('kind') == 'ゲーム内図鑑' for rec in quotes):
            raise ValueError(f'ゲーム内図鑑の説明が必須です: No.{pid:04d}')
        for rec in quotes:
            if rec.get('kind') not in SOURCE_KINDS or not source_is_allowed(rec):
                raise ValueError(f'非対応の出典: {pid} {rec.get("url")}')
            if not all(rec.get(k) for k in ('text', 'source_title')):
                raise ValueError(f'本文・出典の欠落: {pid}')
            # Unapproved legacy source records may lack a review date; never
            # invent a date for them or admit them as playable questions.
            if rec.get('verified_on'):
                parse_date(rec['verified_on'], 'verified_on')
            elif rec.get('quiz_approved') is True:
                raise ValueError(f'出題承認済み記録の照合日がありません: {pid}')
            # '…' is sometimes part of the OFFICIAL original prose (anime previews).
            # Never remove it from a verified direct excerpt. Only explicit editorial
            # omission markers are invalid.
            if '（略）' in rec['text'] or '[省略]' in rec['text']:
                raise ValueError(f'省略した説明文: {pid}')
            if rec['kind'] == 'ポケカ公式':
                # Manually verified species flavor is not age-gated. Do not invent a release date.
                if rec.get('card_text_role') == 'species_flavor':
                    if not (rec.get('quiz_approved') is True and rec.get('verified_on')
                            and rec['url'].startswith('https://www.pokemon-card.com/card-search/details.php/card/')):
                        raise ValueError(f'カード説明文の個別公式出典・確認が不足: {pid}')
                else:
                    parse_date(rec.get('first_release_on'), 'first_release_on')
                    if not rec.get('release_proof_url') or not source_is_allowed({
                        'url': rec['release_proof_url'], 'kind': 'ポケカ公式'}):
                        raise ValueError(f'カードの初登場日を裏付ける公式資料がありません: {pid}')
            if rec['kind'] == '大会公式':
                parse_date(rec.get('event_date'), 'event_date')
    return True


def pokedex_records(row):
    return [q for q in row['quotes'] if q['kind'] in ('ゲーム内図鑑', 'ゲーム内図鑑の補足')]


def supplementary_records(row, today=None):
    """Non-dex sources; species-flavor card texts are age-unlimited, card effects are not."""
    return [q for q in row['quotes'] if q['kind'] not in ('ゲーム内図鑑', 'ゲーム内図鑑の補足') and q.get('quiz_review')!='excluded_verified_wrong_species_assignment' and is_recent(q, today)]


def missing_ids(data, region):
    return sorted((pid for pid in REGIONS[region] if not pokedex_records(data['pokemon'].get(
        str(pid), {'quotes': []}))), key=lambda pid: (isinstance(pid, str), str(pid)))


# Choice-generation hints are only used to SELECT distractors, never shown as facts.
# They are deliberately separate from official source quotations.
import math
from collections import Counter as _TokenCounter
from functools import lru_cache

_CUTE = {906,907,908,909,912,921,922,923,924,925,926,927,
         928,929,931,935,938,939,940,944,963,964,971,974,
         495,498,501,504,506,509,519,531,546,548,550,
         570,572,574,577,580,590,595,602,607,613,627}
_THEME_GROUPS = (
    (r'かわい|可愛|甘え|なつ|懐っこ|拗ね|寂し|きまぐれ|ふわふわ|やんちゃ|気を引|まいぺーす|マイペース', _CUTE),
    (r'炎|ほのお|火炎|火玉|燃え|火を|火の|熱', {494,498,499,500,513,514,554,555,607,608,609,631,636,637,643,909,910,911,935,936,937,1004,'128-paldea-blaze'}),
    (r'電気|でんき|放電|発電|雷|充電|電流', {522,523,587,595,596,602,603,604,618,642,644,921,922,923,938,939,940,941,989,992,995}),
    (r'水中|水面|泳|川|海中|みず|水を|潮|波|水流', {501,502,503,515,516,535,536,537,550,564,565,580,581,592,593,594,647,912,913,914,960,961,963,964,976,977,978,991,'128-paldea-aqua'}),
    (r'草|葉|植物|花|つぼみ|光合成|種子|ツル|木々', {495,496,497,511,512,540,541,542,546,547,548,549,556,585,586,590,591,597,598,640,906,907,908,928,929,930,947,948,949,1011,1019}),
    (r'飛ぶ|羽ばた|翼|ひこう|空中|飛行|風|羽毛', {519,520,521,527,528,561,566,567,580,581,587,627,628,629,630,641,642,940,941,959,962,973}),
    (r'こおり|氷|凍|寒さ|冷たい|雪', {582,583,584,613,614,615,646,974,975,991,996,997,998,1002}),
    (r'毒|どく|有毒|猛毒|毒液|痺れ', {543,544,545,568,569,590,591,966,967,969,970,984,990,'194-paldea'}),
    (r'ゴースト|幽霊|魂|おばけ|生気|怨念|呪', {562,563,592,593,607,608,609,622,623,679,680,681,911,937,971,972,979,986,987}),
    (r'金属|鉄|鋼|はがね|鉱石|ハンマー|磁力', {529,530,597,598,599,600,601,624,625,632,638,957,958,959,966,968,983,994,1000}),
)


@lru_cache(maxsize=8192)
def _ngrams(text):
    text = re.sub(r'[\s　、。！？・「」（）【】0-9a-zA-Z]+', '', text)
    return set(text[i:i+2] for i in range(len(text)-1))


def _semantic_similarity(a, b):
    x, y = _ngrams(a), _ngrams(b)
    if not x or not y:
        return 0.0
    return len(x & y) / math.sqrt(len(x)*len(y))


@lru_cache(maxsize=8192)
def _themes_for(text):
    return [(idx, group) for idx, (pattern, group) in enumerate(_THEME_GROUPS)
            if re.search(pattern, text)]


def distractor_score(db, answer_id, other_id, answer_quote=None, other_quote=None):
    """Rank plausible choices using only official passages and internal group hints."""
    answer_row = db['pokemon'][str(answer_id)]
    other_row = db['pokemon'][str(other_id)]
    anchor = answer_quote['text'] if answer_quote else ' '.join(q['text'] for q in answer_row['quotes'][:3])
    comparison = other_quote['text'] if other_quote else ' '.join(q['text'] for q in other_row['quotes'][:3])
    score = 2.5 * _semantic_similarity(anchor, comparison)
    for _, group in _themes_for(anchor):
        if other_id in group:
            score += 1.7
        if answer_id in group and other_id in group:
            score += 0.5
    # Closely related species usually make more plausible wrong answers.
    if isinstance(answer_id, int) and isinstance(other_id, int):
        dist = abs(answer_id - other_id)
        score += (0.8 if dist == 1 else 0.45 if dist == 2 else 0.15 if dist <= 5 else 0)
    return score


def _prefer_matching_theme(answer_id, candidates, anchor):
    """When three peers exist, require the SAME internally tagged theme.

    This never inserts new factual content into the question; it only changes
    which existing Pokémon can appear as alternative answers.
    """
    for _, group in _themes_for(anchor):
        if answer_id in group:
            preferred = [x for x in candidates if x in group and x != answer_id]
            if len(preferred) >= 3:
                return preferred
    return candidates


def ranked_candidates(db, answer_id, candidates, *, answer_quote=None, quote_for=None, rng=None):
    """Select three UNIQUE, high-similarity distractors with seeded variability."""
    rng = rng or random.Random()
    anchor = (answer_quote['text'] if answer_quote else
              ' '.join(q['text'] for q in db['pokemon'][str(answer_id)]['quotes'][:3]))
    candidates = _prefer_matching_theme(answer_id, candidates, anchor)
    scores = []
    for other_id in candidates:
        if other_id == answer_id:
            continue
        quote = quote_for.get(other_id) if quote_for else None
        score = distractor_score(db, answer_id, other_id, answer_quote, quote)
        scores.append((score + rng.uniform(-0.12, 0.12), other_id))
    scores.sort(reverse=True, key=lambda item: item[0])
    # Randomly draw from top 7 so quizzes don't permanently repeat distractors.
    head = [pid for _, pid in scores[:min(7, len(scores))]]
    rng.shuffle(head)
    return head[:3]


def make_questions(data, region, mode, ids=None, seed=None):
    """Build four-choice questions from unmodified official source records.

    picture:       name/picture -> Pokedex texts
    description:   Pokedex text -> pictured names
    extra_picture: name/picture -> other official-source texts
    extra_description: other official-source text -> pictured names
    identification: picture -> names
    """
    if mode not in ('picture', 'description', 'identification',
                    'extra_description', 'extra_picture', 'extra_mix'):
        raise ValueError('不正な問題形式')
    rng = random.Random(seed)
    region_pool = {pid: pokedex_records(data['pokemon'][str(pid)])
                   for pid in REGIONS[region] if str(pid) in data['pokemon']
                   and pokedex_records(data['pokemon'][str(pid)])}
    extras = {pid: eligible_extra(data['pokemon'][str(pid)]) for pid in region_pool}
    info_mode = mode in ('extra_description', 'extra_picture')
    eligible_pool = {pid: records for pid, records in
                     (extras if info_mode else region_pool).items() if records}
    target = list(ids) if ids is not None else list(eligible_pool)
    absent = [pid for pid in target if pid not in eligible_pool]
    if absent:
        raise ValueError(f'選択した形式に公式文章がないポケモン: {absent[:12]}')
    if len(eligible_pool) < 4:
        raise ValueError('選択肢の作成には4種類以上の公式文章が必要です')
    rng.shuffle(target)
    questions = []
    for pid in target:
        source_pool = eligible_pool if info_mode else region_pool
        answer = rng.choice(source_pool[pid])
        if mode in ('identification', 'description', 'extra_description'):
            candidate_ids = [x for x in eligible_pool if x != pid]
            distractors = ranked_candidates(data, pid, candidate_ids,
                                            answer_quote=answer, rng=rng)
            choices = [pid, *distractors]
            rng.shuffle(choices)
            questions.append({'id':pid,'answer':pid,'choices':choices,
                              'quotes':{pid:answer},'mode':mode})
            continue
        # Image/name -> text. Each wrong quote is officially attributed to
        # another species; select semantically confusing texts when possible.
        candidates = [x for x in eligible_pool if x != pid and
                      any(q['text'] != answer['text'] for q in source_pool[x])]
        candidates = _prefer_matching_theme(pid, candidates, answer['text'])
        quote_for = {}
        for other in candidates:
            unique = [q for q in source_pool[other] if q['text'] != answer['text']]
            quote_for[other] = max(unique, key=lambda q:
                   distractor_score(data, pid, other, answer, q))
        ranked = sorted(candidates, key=lambda x:
            distractor_score(data, pid, x, answer, quote_for[x]) + rng.uniform(-0.12,0.12),
            reverse=True)
        selected = []
        used = {answer['text']}
        for other in ranked:
            quote = quote_for[other]
            if quote['text'] in used:
                continue
            selected.append(other)
            used.add(quote['text'])
            if len(selected) >= 3:
                break
        if len(selected) != 3:
            raise ValueError('異なる公式文章の選択肢が不足しています')
        choices = [pid, *selected]
        rng.shuffle(choices)
        questions.append({'id':pid, 'answer':pid, 'choices':choices,
                          'quotes':{pid:answer, **{x:quote_for[x] for x in selected}},
                          'mode':mode})
    return questions


def national_number(row):
    """A form has its original National Pokédex number, never a fabricated one."""
    return row.get('national_id', row['id'])


_MASK_PATTERN_CACHE = {}

def _mask_pattern(data):
    """Compile Pokémon-name masking once per in-memory database."""
    token=id(data)
    item=_MASK_PATTERN_CACHE.get(token)
    if item is not None and item[0] is data:
        return item[1],item[2]
    names_to_ids={}
    for key, entry in data["pokemon"].items():
        names={entry["name"]}
        if entry.get("base_name"):names.add(entry["base_name"])
        names.update(entry.get("mask_aliases", []))
        for name in names:names_to_ids.setdefault(name,set()).add(key)
    pattern=re.compile("|".join(map(re.escape, sorted(names_to_ids,key=lambda name:(-len(name),name)))))
    _MASK_PATTERN_CACHE.clear()
    _MASK_PATTERN_CACHE[token]=(data,pattern,names_to_ids)
    return pattern,names_to_ids

def display_quote(text, subject_id, data):
    """Mask only the Pokémon being tested. DO NOT change saved official quotes.

    Match known Pokémon names longest first to preserve names of other Pokémon,
    including those containing a shorter name of the subject.
    """
    subject_id = str(subject_id)
    pattern,names_to_ids=_mask_pattern(data)
    return pattern.sub(lambda m: '？？？' if subject_id in names_to_ids[m.group()] else m.group(), text)

def question_passage(rec, pid, data):
    """Quiz-visible complete passage; never alters rec['text'] (official original)."""
    return display_quote(rec.get('question_text') or rec['text'], pid, data)


import csv
import io
import random
from collections import Counter
from datetime import datetime, timezone, timedelta


EXTRA_KINDS = {'ゲーム公式HP', 'アニメ公式', '公式図鑑プロフィール', '公式グッズ紹介', 'ポケモンだいすきクラブ公式記事', '公式小説', '公式短編小説（作中人物の発言）', 'ポケカ公式', 'ポケモン公式大会ニュース'}
ALL_REGION = '両方'
MODE_LABELS = {
    'mix': 'ミックス（図鑑＋図鑑外）',
    'extra_mix': '図鑑外ミックス（全収録情報）',
    'identification': '姿を見て名前を選ぶ',
    'description': '図鑑説明から名前を選ぶ（画像付き）',
    'picture': '姿から図鑑説明を選ぶ',
    'extra_description': '公式情報 → 名前（画像付き）',
    'extra_picture': '名前・姿 → 公式情報',
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
    if mode in ('extra_description', 'extra_picture', 'extra_mix'):
        pool = [p for p in pool if eligible_extra(db['pokemon'][str(p)])]
    return pool


def is_standalone_question(rec):
    """Reject clearly incomplete quotations without changing their original text.

    Editorial/semantic suitability still requires a human review; this is a
    preflight check against the user's reported truncated-choice regressions.
    """
    text = (rec.get('question_text') or rec.get('text') or '').strip()
    return (len(text) >= 18 and text.endswith(('。', '！', '？'))
            and not re.match(r'^(?:その|ここから|どうやら|突如)', text)
            and not text.endswith(('おり', '技です。')))


# Generic move mechanics do not teach players about the particular Pokemon.
# Only the named, confirmed low-value source passages below are suppressed;
# the official original data is preserved verbatim for auditing.
_GENERIC_MOVE_BY_SPECIES = {
    504: ('おさきにどうぞ',),
    511: ('アクロバット',),
    513: ('はじけるほのお',),
    515: ('ねっとう',),
    978: ('いっちょうあがり',),
    602: ('コミュニティ・デイ',),
    # Official page says Raikou's ancestor-like Pokemon *learns* this move;
    # it does not explicitly verify its exclusivity. Avoid claiming 'signature'.
    1021: ('じんらい', '長い首の先にある体毛'),
}

def generic_move_only(rec, row):
    text = rec.get('question_text') or rec.get('text', '')
    return any(term in text for term in _GENERIC_MOVE_BY_SPECIES.get(row['id'], ()))


def eligible_extra(row):
    return [rec for rec in supplementary_records(row)
            if rec['kind'] in EXTRA_KINDS and rec.get('quiz_approved') is True
            and rec.get('quiz_enabled') is not False
            and not generic_move_only(rec, row)
            and is_standalone_question(rec)]


def plan_session(db, region, style, count, *, priority_ids=None, seed=None):
    """Build independent four-choice tasks; the source sentences remain byte-for-byte unchanged.

    priority_ids: restrict to previously missed/bookmarked Pokémon; pools for wrong choices
    remain whole region so even a one-item review can have four choices.
    """
    if style not in MODE_LABELS:
        raise ValueError('不正な出題モード')
    if style in ('extra_description', 'extra_picture', 'extra_mix'):
        return plan_extra_session(db, region, style, count, priority_ids=priority_ids, seed=seed)
    rng = random.Random(seed)
    candidates = pool_ids(db, region, 'extra_description' if style in ('extra_description','extra_picture') else 'description')
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
    modes = ['identification', 'description', 'picture', 'extra_description', 'extra_picture']
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
        if mode in ('extra_description', 'extra_picture'):
            for pid in ids:
                # Mixed quizzes draw one non-dex source record for a species;
                # dedicated non-dex mode tests EVERY approved source record.
                # Mega-only excerpt: no standard-form artwork substitutions.
                compatible_mode = mode
                available = eligible_extra(db['pokemon'][str(pid)])
                if mode == 'extra_picture' and not any(not _extra_no_art(r) for r in available):
                    compatible_mode = 'extra_description'
                choices = plan_extra_session(db, one_region, compatible_mode,
                     '全問', priority_ids=[pid], seed=rng.getrandbits(64))
                q = rng.choice(choices)
                indexed[str(pid)] = q
            continue
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




def extra_record_count(db, region):
    """Number of approved distinct source passages, not just Pokemon species."""
    return sum(len(eligible_extra(db['pokemon'][str(pid)])) for pid in pool_ids(db, region, 'description'))


def _extra_no_art(rec):
    return bool(rec.get('require_special_form_image'))


def plan_extra_session(db, region, style, count, *, priority_ids=None, seed=None):
    """One question PER official excerpt; source strings stay unchanged.

    For excerpts describing Mega species, fall back to text-only species choices,
    not a picture of the base species or an invented special sprite.
    """
    if style not in ('extra_description', 'extra_picture', 'extra_mix'):
        raise ValueError('図鑑外モードの指定が不正です')
    rng=random.Random(seed)
    regions=REGIONS if region==ALL_REGION else {region:REGIONS[region]}
    targets=[]
    for one_region, species in regions.items():
        for pid in species:
            for idx, rec in enumerate(eligible_extra(db['pokemon'][str(pid)])):
                # Image->official info disallowed when the excerpt is about
                # a Mega species not represented by the artwork in this app.
                if style=='extra_picture' and _extra_no_art(rec):
                    continue
                targets.append((one_region,pid,idx,rec))
    if priority_ids is not None:
        wanted={str(pid) for pid in priority_ids}
        targets=[t for t in targets if str(t[1]) in wanted]
    rng.shuffle(targets)
    if count!='全問':
        if not isinstance(count,int) or count<1:raise ValueError('問題数が不正です')
        targets=targets[:count]
    questions=[]
    for one_region,pid,idx,answer in targets:
        mode=style if style!='extra_mix' else rng.choice(['extra_description','extra_picture'])
        if _extra_no_art(answer):mode='extra_description'
        regional_ids=REGIONS[one_region]
        if mode=='extra_picture':
            pool={p:[r for r in eligible_extra(db['pokemon'][str(p)]) if not _extra_no_art(r)]
                  for p in regional_ids}
            pool={p:rs for p,rs in pool.items() if rs}
            def select_other(p):
                recs=[r for r in pool[p] if question_passage(r,p,db)!=question_passage(answer,pid,db)]
                if not recs:return None
                return max(recs,key=lambda r:distractor_score(db,pid,p,answer,r))
            quote_for={p:select_other(p) for p in pool if p!=pid}
            quote_for={p:r for p,r in quote_for.items() if r is not None}
            ordered=ranked_candidates(db,pid,list(quote_for),answer_quote=answer,
                                      quote_for=quote_for,rng=rng)
            for p in list(quote_for):
                if p not in ordered:ordered.append(p)
            chosen=[]; used={question_passage(answer,pid,db)}
            for other in ordered:
                shown=question_passage(quote_for[other],other,db)
                if shown in used:continue
                used.add(shown);chosen.append(other)
                if len(chosen)==3:break
            if len(chosen)<3:raise ValueError(f'図鑑外の異なる文章が不足: {pid}')
            ids=[pid,*chosen];rng.shuffle(ids)
            questions.append({'id':pid,'answer':pid,'choices':ids,
                              'quotes':{pid:answer, **{x:quote_for[x] for x in chosen}},
                              'mode':mode,'source_record_index':idx})
        else:
            pool=[p for p in regional_ids if p!=pid and eligible_extra(db['pokemon'][str(p)])]
            # If named in the passage, another species must not be a choice.
            names_in_text={p for p in pool if db['pokemon'][str(p)]['name'] in (answer.get('question_text') or answer['text'])}
            pool=[p for p in pool if p not in names_in_text]
            chosen=ranked_candidates(db,pid,pool,answer_quote=answer,rng=rng)
            if len(chosen)<3:raise ValueError(f'図鑑外選択肢不足: {pid}')
            ids=[pid,*chosen];rng.shuffle(ids)
            questions.append({'id':pid,'answer':pid,'choices':ids,'quotes':{pid:answer},
                              'mode':mode,'source_record_index':idx,
                              'force_text_choices':_extra_no_art(answer)})
    return questions
