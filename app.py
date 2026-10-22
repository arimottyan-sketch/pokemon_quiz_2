"""Quiz and Pokémon information browser. Source texts are kept unchanged."""
import random
import requests
import streamlit as st

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
APPROVED_HOSTS = {'zukan.pokemon.co.jp', 'www.pokemon.co.jp', 'www.pokemon-card.com', 'www.tv-tokyo.co.jp'}
SOURCE_KINDS = {'ゲーム内図鑑', 'ゲーム公式HP', 'ポケカ公式', 'アニメ公式', '大会公式', '公式図鑑プロフィール', 'ゲーム内図鑑の補足', '公式グッズ紹介'}
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
    """図鑑や公式設定は年代無制限。カードと大会実績だけ近3年に限定。"""
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
            if not all(rec.get(k) for k in ('text', 'source_title', 'verified_on')):
                raise ValueError(f'本文・出典・照合日の欠落: {pid}')
            parse_date(rec['verified_on'], 'verified_on')
            # '…' is sometimes part of the OFFICIAL original prose (anime previews).
            # Never remove it from a verified direct excerpt. Only explicit editorial
            # omission markers are invalid.
            if '（略）' in rec['text'] or '[省略]' in rec['text']:
                raise ValueError(f'省略した説明文: {pid}')
            if rec['kind'] == 'ポケカ公式':
                parse_date(rec.get('first_release_on'), 'first_release_on')
                if not rec.get('release_proof_url') or not source_is_allowed({
                    'url': rec['release_proof_url'], 'kind': 'ポケカ公式'}):
                    raise ValueError(f'カードの初登場日を裏付ける公式資料がありません: {pid}')
            if rec['kind'] == '大会公式':
                parse_date(rec.get('event_date'), 'event_date')
    return True


def pokedex_records(row):
    return [q for q in row['quotes'] if q['kind'] == 'ゲーム内図鑑']


def supplementary_records(row, today=None):
    """公式HP/アニメは無期限、カード・大会は3年以内のもののみ。"""
    return [q for q in row['quotes'] if q['kind'] != 'ゲーム内図鑑' and is_recent(q, today)]


def missing_ids(data, region):
    return sorted((pid for pid in REGIONS[region] if not pokedex_records(data['pokemon'].get(
        str(pid), {'quotes': []}))), key=lambda pid: (isinstance(pid, str), str(pid)))


# Choice-generation hints are only used to SELECT distractors, never shown as facts.
# They are deliberately separate from official source quotations.
import math
from collections import Counter as _TokenCounter

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


def _ngrams(text):
    text = re.sub(r'[\s　、。！？・「」（）【】0-9a-zA-Z]+', '', text)
    return set(text[i:i+2] for i in range(len(text)-1))


def _semantic_similarity(a, b):
    x, y = _ngrams(a), _ngrams(b)
    if not x or not y:
        return 0.0
    return len(x & y) / math.sqrt(len(x)*len(y))


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
                    'extra_description', 'extra_picture'):
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


def display_quote(text, subject_id, data):
    """Mask only the Pokémon being tested. DO NOT change saved official quotes.

    Match known Pokémon names longest first to preserve names of other Pokémon,
    including those containing a shorter name of the subject.
    """
    subject_id = str(subject_id)
    names_to_ids = {}
    for key, entry in data['pokemon'].items():
        names = {entry['name']}
        if entry.get('base_name'):
            names.add(entry['base_name'])
        for alias in entry.get('mask_aliases', []):
            names.add(alias)
        for name in names:
            names_to_ids.setdefault(name, set()).add(key)
    if not names_to_ids:
        return text
    pattern = re.compile('|'.join(map(re.escape, sorted(names_to_ids, key=lambda name: (-len(name), name)))))
    return pattern.sub(lambda m: '？？？' if subject_id in names_to_ids[m.group()] else m.group(), text)

import csv
import io
import random
from collections import Counter
from datetime import datetime, timezone, timedelta


EXTRA_KINDS = {'ゲーム公式HP', 'アニメ公式', 'ゲーム内図鑑の補足', '公式図鑑プロフィール', '公式グッズ紹介'}
ALL_REGION = '両方'
MODE_LABELS = {
    'mix': 'ミックス',
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
    if mode in ('extra_description', 'extra_picture'):
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


st.set_page_config(page_title='イッシュ・パルデア｜クイズとポケモン情報', page_icon='📘', layout='centered')
# GitHub's browser upload may reject .streamlit/: keep the color palette in
# a regular file and apply it to the page without any dot-prefixed upload path.
from pathlib import Path
_THEME_PATH = Path(__file__).with_name('theme.css')
if _THEME_PATH.is_file():
    st.markdown('<style>\n' + _THEME_PATH.read_text(encoding='utf-8') + '\n</style>',
                unsafe_allow_html=True)

NAME_MODE = '名前入力'
PICTURE_MODE = MODE_LABELS['picture']
TEXT_MODE = MODE_LABELS['description']

try:
    db = read_db()
except (OSError, ValueError) as error:
    st.error(f'公式文章の固定データを読み込めません。data/official_quotes.json を確認してください。詳細：{error}')
    st.stop()

for key, default in {
    'specs':None, 'idx':0, 'score':0, 'answer':None,
    'missed':[], 'bookmarked':[], 'history':[], 'is_review':False,
    'region':'両方', 'quiz_style':'mix', 'finished':False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

@st.cache_data(ttl=86400, show_spinner=False)
def form_art(slug):
    """Only obtain artwork from PokeAPI. Never use the base form as a fallback."""
    try:
        r = requests.get(f'https://pokeapi.co/api/v2/pokemon/{slug}', timeout=10)
        r.raise_for_status()
        s = r.json().get('sprites') or {}
        return (((s.get('other') or {}).get('official-artwork') or {}).get('front_default')
                or ((s.get('other') or {}).get('home') or {}).get('front_default')
                or s.get('front_default'))
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def artwork(row):
    if row.get('pokeapi_slug'):
        return form_art(row['pokeapi_slug'])
    return ('https://raw.githubusercontent.com/PokeAPI/sprites/master/'
            f'sprites/pokemon/other/official-artwork/{national_number(row)}.png')


def art_display(row, *, full=False):
    url = artwork(row)
    if url:
        if full:
            st.image(url, use_container_width=True)
        else:
            st.image(url, width=260)
    else:
        st.caption('この姿の画像を取得できませんでした（通常の姿で代用していません）。')


def source(rec):
    st.caption(f"出典：{rec['source_title']}｜{rec['kind']}")
    if rec.get('source_scope'):
        st.caption(f"資料の読み方：{rec['source_scope']}")
    st.markdown(f"[公式の掲載ページ ↗]({rec['url']})")


def clear_question_only():
    st.session_state.specs = None
    st.session_state.idx = 0
    st.session_state.answer = None
    st.session_state.finished = False


def start(region, style, count, review_ids=None):
    if style == 'typed':
        # Hand-typed spelling training retains the earlier style without a PokeAPI
        # species/name lookup: names come from the local official-source dataset.
        ids = pool_ids(db, region, 'description')
        if review_ids is not None:
            allowed = {str(p) for p in review_ids}
            ids = [x for x in ids if str(x) in allowed]
        random.shuffle(ids)
        if isinstance(count,int):
            ids = ids[:count]
        specs = [{'id':x, 'mode':'typed', 'choices':[], 'quotes':{}} for x in ids]
    else:
        specs = plan_session(db, region, style, count, priority_ids=review_ids)
    if not specs:
        st.warning('出題できるポケモンがありません。地方や問題形式を変更してください。')
        return
    st.session_state.specs = specs
    st.session_state.idx = 0
    st.session_state.score = 0
    st.session_state.answer = None
    st.session_state.finished = False
    st.session_state.is_review = review_ids is not None
    st.session_state.region = region
    st.session_state.quiz_style = style
    st.rerun()


def commit(selection):
    if st.session_state.answer is not None:
        return
    q = st.session_state.specs[st.session_state.idx]
    ok = (selection == q['id'])
    st.session_state.answer = ok
    if ok:
        st.session_state.score += 1
        if st.session_state.is_review and q['id'] in st.session_state.missed:
            st.session_state.missed.remove(q['id'])
    elif q['id'] not in st.session_state.missed:
        st.session_state.missed.append(q['id'])
    st.session_state.history.append(make_history(q['id'],q['mode'],ok))
    st.rerun()


def details(pid, main_quote=None):
    row = db['pokemon'][str(pid)]
    if main_quote:
        st.markdown('**この問題の公式掲載文**')
        st.write(main_quote['text'])
        source(main_quote)
    else:
        for rec in pokedex_records(row):
            st.write(rec['text'])
            source(rec)
    extras = supplementary_records(row)
    if extras:
        with st.expander(f'もっと知る｜その他の公式情報（{len(extras)}件）'):
            for j, rec in enumerate(extras):
                if j:
                    st.divider()
                st.write(rec['text'])
                source(rec)


def bookmark_button(pid):
    saved = pid in st.session_state.bookmarked
    if st.button('★ 復習リストから外す' if saved else '☆ あとで復習する', key=f'bookmark_{pid}_{st.session_state.idx}'):
        if saved:
            st.session_state.bookmarked.remove(pid)
        else:
            st.session_state.bookmarked.append(pid)
        st.rerun()


def show_question(q):
    pid = q['id']
    row = db['pokemon'][str(pid)]
    kind = q['mode']
    n = st.session_state.idx
    total = len(st.session_state.specs)
    st.progress(n / total, text=f'{n+1} / {total}問 ｜ 正解 {st.session_state.score}問')
    st.caption(f"{MODE_LABELS.get(kind, NAME_MODE)} ・ {region_for(pid)}")
    answered = st.session_state.answer is not None
    if kind in ('identification','typed'):
        st.markdown('#### このポケモンの名前は？')
        art_display(row)
    elif kind in ('picture', 'extra_picture'):
        st.markdown('#### このポケモンに当てはまる公式情報を選んでください' if kind == 'extra_picture' else
                    '#### このポケモンに当てはまる図鑑説明を選んでください')
        art_display(row)
    else:
        st.markdown('#### この公式の文章は、どのポケモンのもの？')
        st.write(display_quote(q['quotes'][pid]['text'], pid, db))
        st.caption('※正解の名前が文章中に登場する場合は、問題画面でのみ伏せています。')

    if kind == 'typed':
        with st.form(f'write_{n}'):
            answer_text = st.text_input('カタカナで名前を入力', disabled=answered, autocomplete='off')
            submit = st.form_submit_button('回答する', disabled=answered, type='primary')
        if submit:
            # No aliases silently accepted: spelling practice is exact.
            chosen = pid if answer_text.strip() == row['name'] else None
            commit(chosen)
    elif kind in ('description', 'extra_description'):
        # Image-backed four answer buttons; no hidden preselected radio values.
        submitted_choice = None
        with st.form(f'four_{n}'):
            for row_start in (0,2):
                cols = st.columns(2, gap='small')
                for offset,col in enumerate(cols):
                    choice_index = row_start + offset
                    choice_pid = q['choices'][choice_index]
                    option = db['pokemon'][str(choice_pid)]
                    with col:
                        art_display(option, full=True)
                        st.markdown(f"**{'ABCD'[choice_index]}. {option['name']}**")
                        if st.form_submit_button(f"{'ABCD'[choice_index]}を選ぶ",disabled=answered,
                                                 use_container_width=True):
                            submitted_choice = choice_pid
        if submitted_choice is not None:
            commit(submitted_choice)
    else:
        with st.form(f'four_{n}'):
            if kind in ('picture','extra_picture'):
                labels = [display_quote(q['quotes'][p]['text'], p, db) for p in q['choices']]
            else:
                labels = [db['pokemon'][str(p)]['name'] for p in q['choices']]
            choice = st.radio('選択肢', list(range(4)),
                              format_func=lambda k:f"{'ABCD'[k]}. {labels[k]}",
                              key=f'choice_{n}',disabled=answered,index=None)
            submit = st.form_submit_button('回答する', disabled=answered,
                                           type='primary')
        if submit and choice is not None:
            commit(q['choices'][choice])
    if answered:
        ok=st.session_state.answer
        (st.success if ok else st.error)(('正解！' if ok else f"正解は {row['name']}"))
        st.markdown(f"### No.{national_number(row):04d} {row['name']}")
        if kind != 'typed':
            details(pid,q['quotes'][pid] if kind!='identification' else None)
        else:
            details(pid)
        bookmark_button(pid)
        if kind in ('picture','extra_picture'):
            with st.expander('他の選択肢の出典'):
                for x in q['choices']:
                    if x != pid:
                        st.markdown(f"**{db['pokemon'][str(x)]['name']}**")
                        source(q['quotes'][x])
        col_next, col_finish = st.columns([2,1])
        with col_next:
            next_clicked = st.button('次の問題へ →',type='primary',use_container_width=True)
        with col_finish:
            finish_clicked = st.button('ここまでで終了',type='secondary',use_container_width=True)
        if finish_clicked:
            st.session_state.finished = True
            st.rerun()
        if next_clicked:
            st.session_state.idx += 1
            st.session_state.answer = None
            if st.session_state.idx >= total:
                st.session_state.finished = True
            st.rerun()
    else:
        if st.button('ここまでで終了',type='secondary'):
            st.session_state.finished=True
            st.rerun()


def show_finish():
    st.header('結果')
    specs=st.session_state.specs
    attempted = min(st.session_state.idx + (1 if st.session_state.answer is not None else 0), len(specs))
    if st.session_state.finished and st.session_state.idx>=len(specs):
        attempted=len(specs)
    c1,c2,c3 = st.columns(3)
    c1.metric('解答数',attempted)
    c2.metric('正解',st.session_state.score)
    c3.metric('正答率',f'{st.session_state.score/attempted:.0%}' if attempted else '—')
    pending = list(dict.fromkeys(st.session_state.missed + st.session_state.bookmarked))
    st.write(f'現在の復習対象：**{len(pending)}種類・すがた**（誤答と★登録）')
    if pending:
        st.caption('復習で正解したものは誤答リストから外れます。★登録したものは手動で外すまで残ります。')
        if st.button('苦手・★登録したポケモンを復習',type='primary'):
            start(ALL_REGION, 'mix', '全問',review_ids=pending)
    if st.session_state.history:
        st.download_button('回答履歴をCSVで保存', data=progress_csv(st.session_state.history,db).encode('utf-8'),
                           file_name='pokemon_quiz_history.csv',mime='text/csv')
        st.caption('回答履歴はページを閉じると消える場合があります。必要に応じてCSVを保存してください。')
    if st.button('新しいクイズを始める'):
        clear_question_only()
        st.rerun()


st.title('イッシュ・パルデア')
page = st.radio('画面', ['クイズ', 'ポケモン情報', '使い方'], horizontal=True,
                label_visibility='collapsed')

if page == 'クイズ':
    if st.session_state.specs is None:
        with st.form('quiz_options'):
            region = st.selectbox('出題する地方', [ALL_REGION,'イッシュ','パルデア'], index=0)
            options = list(MODE_LABELS.values()) + [NAME_MODE]
            mode_label = st.selectbox('問題形式', options, index=0)
            mode = 'typed' if mode_label == NAME_MODE else DISPLAY_MODES[mode_label]
            count = st.selectbox('問題数', [5,10,20,30,'全問'], index=1,
                                 format_func=lambda n:f'{n}問' if isinstance(n,int) else '全問')
            marked = list(dict.fromkeys(st.session_state.missed+st.session_state.bookmarked))
            restrict = st.checkbox(f'苦手・★登録だけ出題する（{len(marked)}種類・すがた）',
                                   disabled=not marked)
            available = pool_ids(db,region,mode if mode!='typed' else 'description')
            if restrict:
                allowed = {str(p) for p in marked}
                available = [p for p in available if str(p) in allowed]
            st.caption(f'この設定での出題対象：{len(available)}種類・すがた')
            begin = st.form_submit_button('クイズを始める', type='primary', disabled=not available,
                                          use_container_width=True)
        if begin:
            start(region,mode,count, review_ids=marked if restrict else None)
    elif st.session_state.finished or st.session_state.idx >= len(st.session_state.specs):
        show_finish()
    else:
        show_question(st.session_state.specs[st.session_state.idx])

elif page == 'ポケモン情報':
    st.subheader('ポケモン情報')
    region = st.selectbox('地方で絞り込む',[ALL_REGION,'イッシュ','パルデア'],key='lookup_region')
    search = st.text_input('ポケモン名・図鑑番号・文章中の言葉で検索',placeholder='例：ケンタロス、128、ツル',key='lookup_search')
    ids = pool_ids(db, region, 'description')
    if search.strip():
        needle = search.strip().lower()
        ids = [p for p in ids if needle in db['pokemon'][str(p)]['name'].lower()
               or needle in str(national_number(db['pokemon'][str(p)]))
               or any(needle in r['text'].lower() for r in db['pokemon'][str(p)]['quotes'])]
    ids = sorted(ids,key=lambda p:(national_number(db['pokemon'][str(p)]),str(p)))
    st.caption(f'検索結果：{len(ids)}種類・すがた')
    if ids:
        selection = st.selectbox('確認したいポケモン',ids,
             format_func=lambda p:f"No.{national_number(db['pokemon'][str(p)]):04d}　{db['pokemon'][str(p)]['name']}")
        selected = db['pokemon'][str(selection)]
        st.markdown(f"### {selected['name']}")
        art_display(selected)
        st.caption(f"全国図鑑 No.{national_number(selected):04d}｜{region_for(selection)}")
        extras = supplementary_records(selected)
        if extras:
            st.markdown('#### もっと詳しく｜公式サイト・作品情報')
            for rec in extras:
                st.write(rec['text'])
                source(rec)
        st.markdown('#### ゲーム内図鑑')
        for rec in pokedex_records(selected):
            st.write(rec['text'])
            source(rec)
        c1,c2 = st.columns(2)
        with c1:
            if st.button('このポケモンで1問',use_container_width=True):
                start(region_for(selection),'description',1,review_ids=[selection])
        with c2:
            saved=selection in st.session_state.bookmarked
            if st.button('★ 復習リストから外す' if saved else '☆ あとで復習',use_container_width=True):
                if saved:st.session_state.bookmarked.remove(selection)
                else:st.session_state.bookmarked.append(selection)
                st.rerun()
    else:
        st.warning('該当するポケモンがありません。表記や地方を変えて検索してください。')

else:
    st.subheader('使い方')
    st.markdown('''
- **クイズ**：地方・問題形式・問題数を選んでスタート。回答後に正解と出典を表示します。
- **ポケモン情報**：名前・図鑑番号・説明文で検索し、掲載文と参照先を確認できます。
- **復習**：間違えたポケモンや★登録したポケモンを、クイズの出題対象に指定できます。
- **公式情報**：『公式情報 → 名前』と『名前・姿 → 公式情報』の両方を出題できます。
- **回答履歴**：結果画面からCSVを保存できます。
''')
