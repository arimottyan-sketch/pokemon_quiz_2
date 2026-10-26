"""Opt-in progressively revealed clue quiz. Verified source quotes remain untouched.

Official type/ability data is read from the Pokémon Company's public Pokédex.
No non-official game metadata is used as a substitute when this lookup fails.
"""
import random
import re
from html import unescape

from quiz_engine import (REGIONS, ALL_REGION, eligible_extra, pokedex_records,
                         question_passage, ranked_candidates)

PROGRESSIVE_MODE = 'progressive'
PROGRESSIVE_LABEL = 'だんだんヒント（このポケモンは誰？）'
TYPE_LABELS = frozenset('ノーマル くさ ほのお みず でんき むし ひこう いわ どく じめん こおり かくとう エスパー ゴースト ドラゴン あく はがね フェアリー'.split())
MAX_HINTS = 5

# Small local cache of facts directly checked against official zukan pages.
# Others are loaded on demand from each species' own official Pokédex page.
OFFICIALLY_CHECKED = {
    '649': {'types': ['むし', 'はがね'], 'abilities': ['ダウンロード'], 'url': 'https://zukan.pokemon.co.jp/detail/0649'},
    '909': {'types': ['ほのお'], 'abilities': ['もうか'], 'url': 'https://zukan.pokemon.co.jp/detail/0909'},
}


def progressive_pair(db, pid):
    """Require two distinct eligible passages: no fabricated / repeated second clue."""
    row = db['pokemon'][str(pid)]
    dex = [r for r in pokedex_records(row) if len((r.get('text') or '').strip()) >= 12]
    extra = [r for r in eligible_extra(row)
             if not r.get('require_special_form_image') and r.get('quiz_enabled') is not False]
    # Prefer story/ecology facts for the harder first clue; official dex as follow-up.
    pairs = [(r, d) for r in extra for d in dex
             if question_passage(r, pid, db) != question_passage(d, pid, db)]
    if pairs:
        def interest(rec):
            label = (rec.get('source_title', '') + ' ' + rec.get('source_scope', '')).lower()
            # Staff-conversation priority: movie / ecology over incidental
            # appearance records from minor puzzle and mobile games.
            if 'ポケとる' in label or 'pokémon go' in label or 'pokemon go' in label:
                return 0
            if any(w in label for w in ('劇場版', '映画', '短編映画')):
                return 4
            if rec['kind'] in ('アニメ公式', 'ゲーム公式HP', 'ポケモンだいすきクラブ公式記事'):
                return 3
            return 2
        return max(pairs, key=lambda p: (interest(p[0]),
                                          len(question_passage(p[0], pid, db)),
                                          len(question_passage(p[1], pid, db))))
    # Two original game dex entries: prefer an informative one first, a shorter second.
    unique = []
    for rec in dex:
        if question_passage(rec, pid, db) not in [question_passage(x, pid, db) for x in unique]:
            unique.append(rec)
    if len(unique) < 2:
        return None
    ranked = sorted(unique, key=lambda r: len(question_passage(r, pid, db)), reverse=True)
    return ranked[0], ranked[-1]


def progressive_ids(db, region, priority_ids=None):
    regions = REGIONS if region == ALL_REGION else {region: REGIONS[region]}
    allowed = None if priority_ids is None else {str(x) for x in priority_ids}
    return [pid for ids in regions.values() for pid in ids
            if str(pid) in db['pokemon'] and (allowed is None or str(pid) in allowed)
            and progressive_pair(db, pid) is not None]


def plan_progressive_session(db, region, count, priority_ids=None, seed=None):
    rng = random.Random(seed)
    ids = progressive_ids(db, region, priority_ids)
    rng.shuffle(ids)
    if count != '全問':
        if not isinstance(count, int) or count < 1:
            raise ValueError('問題数が不正です')
        ids = ids[:count]
    output = []
    for pid in ids:
        pair = progressive_pair(db, pid)
        region_ids = REGIONS['イッシュ' if isinstance(pid, int) and 494 <= pid < 650 else 'パルデア']
        # Do not list a Pokémon explicitly named in either clue as a distractor.
        passages = ' '.join(question_passage(rec, pid, db) for rec in pair)
        candidates = [p for p in region_ids if p != pid
                      and db['pokemon'][str(p)]['name'] not in passages
                      and not (db['pokemon'][str(p)].get('base_name')
                               and db['pokemon'][str(p)]['base_name'] in passages)]
        distractors = ranked_candidates(db, pid, candidates,
                                        answer_quote=pair[0], rng=rng)
        if len(distractors) != 3:
            raise ValueError(f'{pid}: 四択を作れません')
        options = [pid] + distractors
        rng.shuffle(options)
        output.append({'id': pid, 'answer': pid, 'mode': PROGRESSIVE_MODE,
                       'choices': options, 'quotes': {}, 'hints': list(pair)})
    return output


def official_zukan_url(row):
    dex = pokedex_records(row)
    for rec in dex:
        url = rec.get('url', '')
        if re.fullmatch(r'https://zukan\.pokemon\.co\.jp/detail/[\w-]+/?', url):
            return url
    return None


def parse_official_zukan_html(html, url):
    """Extract only values explicitly present near official profile labels.

    Fail closed on ambiguous sites/markup; never infer a type/ability from the name.
    """
    if not re.fullmatch(r'https://zukan\.pokemon\.co\.jp/detail/[\w-]+/?', url or ''):
        return None
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'template']):
        tag.decompose()
    lines = [re.sub(r'\s+', ' ', unescape(s)).strip() for s in soup.stripped_strings]
    # Remove nav text by seeking the first numbered heading.
    head = next((i for i, s in enumerate(lines) if re.match(r'^No\.?\s*\d{3,4}', s)), None)
    if head is None:
        return None
    lines = lines[head:head + 100]
    def key(s):
        return s.replace('：','').replace(':','').strip()
    def seek(label, start=0):
        return next((i for i in range(start, len(lines)) if key(lines[i]) == label), None)
    t_i = seek('タイプ')
    h_i = seek('高さ', t_i + 1) if t_i is not None else None
    a_i = seek('特性')
    if t_i is None or h_i is None or not (0 < h_i-t_i <= 12):
        return None
    types=[]
    for fragment in lines[t_i+1:h_i]:
        for part in re.split(r'[\s、・/]+', fragment):
            if part in TYPE_LABELS and part not in types:
                types.append(part)
    if not 1 <= len(types) <= 2:
        return None
    abilities=[]
    if a_i is not None:
        # Only take the first short non-label value following the '特性' field.
        # The official page lists a heading and prose for each ability afterward.
        for fragment in lines[a_i+1:a_i+9]:
            cleaned = fragment.replace('?', '').strip()
            if cleaned in ('特性','とくせい','特性とは',''):
                continue
            if (2 <= len(cleaned) <= 14 and not re.search(r'[。！？、:：\d]', cleaned)
                    and not any(c.isspace() for c in cleaned)):
                abilities.append(cleaned)
                break
    return {'types':types, 'abilities':abilities, 'url':url}


def get_official_profile(row, fetch):
    """fetch(url) -> html; caller caches fetch result. No PokeAPI factual fallback."""
    url = official_zukan_url(row)
    if not url:
        return None
    known = OFFICIALLY_CHECKED.get(str(row['id']))
    if known and known['url'] == url:
        return dict(known)
    try:
        return parse_official_zukan_html(fetch(url), url)
    except Exception:
        return None


def hint_points(step, informative_steps):
    """Starts at five; no point deduction for unavailable official hints."""
    return max(1, 5 - sum(i in informative_steps for i in range(1, step + 1)))
