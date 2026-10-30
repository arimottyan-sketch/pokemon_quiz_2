"""Opt-in progressively revealed clue quiz. Verified source quotes remain untouched.

Official type/ability data is read from the Pokémon Company's public Pokédex.
No non-official game metadata is used as a substitute when this lookup fails.
"""
import random
import re
import json
from pathlib import Path
from html import unescape

from quiz_engine import (REGIONS, ALL_REGION, eligible_extra, pokedex_records,
                         question_passage, ranked_candidates)

PROGRESSIVE_MODE = 'progressive'
PROGRESSIVE_LABEL = 'だんだんヒント（このポケモンは誰？）'
TYPE_LABELS = frozenset('ノーマル くさ ほのお みず でんき むし ひこう いわ どく じめん こおり かくとう エスパー ゴースト ドラゴン あく はがね フェアリー'.split())
MAX_HINTS = 5

# Small local cache of facts directly checked against official zukan pages.
# These are ALL abilities DISPLAYED ON THE SOURCE PAGE, not a promise that
# hidden abilities (which are often absent from that page) were checked.
# Others are loaded on demand from each species' own official Pokédex page.
OFFICIALLY_CHECKED = {
    '649': {'types': ['むし', 'はがね'], 'abilities': ['ダウンロード'], 'url': 'https://zukan.pokemon.co.jp/detail/0649'},
    '506': {'types': ['ノーマル'], 'abilities': ['やるき', 'ものひろい'], 'url': 'https://zukan.pokemon.co.jp/detail/0506'},
    '909': {'types': ['ほのお'], 'abilities': ['もうか'], 'url': 'https://zukan.pokemon.co.jp/detail/0909'},
}


# Each addition below has been checked on the Pokémon Company's own site.
# These five species are fixed for offline use. Other species are NOT assumed
# to have no hidden ability just because the official zukan omits one.
_VERIFIED_HIDDEN_FILE = Path(__file__).resolve().parent / 'data' / 'official_verified_hidden_abilities_20261026.json'
_VERIFIED_HIDDEN = json.loads(_VERIFIED_HIDDEN_FILE.read_text(encoding='utf-8'))['records']
_VERIFIED_EXTRA = json.loads((_VERIFIED_HIDDEN_FILE.parent / 'official_verified_supplemental_ability_20261026.json').read_text(encoding='utf-8'))['records']
_OFFICIAL_PROFILE_OCT28 = json.loads((_VERIFIED_HIDDEN_FILE.parent / 'official_zukan_profiles_checked_20261028.json').read_text(encoding='utf-8'))['records']
# User explicitly permits the named secondary source ONLY for ability information.
_PERMITTED_ABILITY_EXCEPTION = json.loads((_VERIFIED_HIDDEN_FILE.parent / 'permitted_ability_exception_20261030.json').read_text(encoding='utf-8'))['records']


def attach_official_hidden(profile, row):
    """Merge species-specific source-checked hidden abilities, never guessing any."""
    if not profile:
        return None
    output = dict(profile)
    evidence = _VERIFIED_HIDDEN.get(str(row['id']))
    output.setdefault('hidden_abilities', [])
    output.setdefault('hidden_source_urls', [])
    output.setdefault('hidden_abilities_verified', False)
    supplement = _VERIFIED_EXTRA.get(str(row['id']))
    if supplement and supplement['name'] == row['name']:
        output['additional_official_abilities'] = list(supplement['additional_abilities'])
        output['additional_official_source_urls'] = [supplement['source_url']]
        for skill in supplement['additional_abilities']:
            if skill not in output['abilities']:
                output['abilities'] = output['abilities'] + [skill]
    if (not evidence or row['name'] != evidence['name']
            or output.get('url') != evidence['zukan_url']):
        return output
    for skill in evidence['hidden_abilities']:
        if skill not in output['abilities']:
            output['abilities'] = output['abilities'] + [skill]
    output['hidden_abilities'] = list(evidence['hidden_abilities'])
    output['hidden_source_urls'] = [evidence['source_url']]
    output['hidden_abilities_verified'] = True
    output['abilities_scope'] = 'official_zukan_plus_species_verified_hidden'
    return output



def staged_official_quote(rec):
    """Create two progressively longer quotations from ONE existing official record.

    Used only when an independent second official record is unavailable.
    Neither stage is represented as a newly sourced fact.
    """
    original = rec['text'].strip()
    if not original:
        return None
    # Prefer the first complete sentence; show the rest at the second stage.
    first_end = original.find('。')+1
    if not (max(12, len(original)//5) <= first_end <= len(original)*.85):
        # With a one-sentence source, reveal its first clause first. Exact prefix
        # only; the ellipsis denotes UI truncation, not original punctuation.
        pivots=[m.end() for m in re.finditer(r'[　 、，]',original)
                if len(original)*.35 <= m.end() <= len(original)*.7]
        first_end=min(pivots,key=lambda x:abs(x-len(original)*.52)) if pivots else max(10,len(original)//2)
    first=original[:first_end].rstrip()
    if not first or len(first) >= len(original):
        return None
    one=dict(rec, question_text=first+'…', progressive_staged=True)
    two=dict(rec, progressive_staged=True)
    return one,two

def progressive_pair(db, pid):
    """Require two distinct eligible passages: no fabricated / repeated second clue."""
    row = db['pokemon'][str(pid)]
    dex = [r for r in pokedex_records(row) if len((r.get('text') or '').strip()) >= 12]
    extra = [r for r in eligible_extra(row)
             if (not r.get('require_special_form_image') or r.get('progressive_allow_mega_hint') is True) and r.get('quiz_enabled') is not False]
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
        selected = max(pairs, key=lambda p: (p[0].get('progressive_priority', 0), interest(p[0]),
                                              len(question_passage(p[0], pid, db)),
                                              len(question_passage(p[1], pid, db))))
        # Only an explicitly approved per-record exception reverses dex/episode order.
        return (selected[1], selected[0]) if selected[0].get('progressive_after_dex') is True else selected
    # Two original game dex entries: prefer an informative one first, a shorter second.
    unique = []
    for rec in dex:
        if question_passage(rec, pid, db) not in [question_passage(x, pid, db) for x in unique]:
            unique.append(rec)
    if len(unique) < 2:
        return staged_official_quote(unique[0]) if unique else None
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
    # The original quote for Landorus is sourced from Therian Forme,
    # but the quiz artwork/entry is the base Incarnate Forme.
    # Select the explicitly verified matching official profile only for hints.
    if row.get('id') == 645 and row.get('name') == 'ランドロス':
        return 'https://zukan.pokemon.co.jp/detail/0645'
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
    abilities = []
    if a_i is not None:
        # The official zukan prints each displayed ability twice:
        #   特性： → やるき → ? → 特性 → やるき → (explanation)
        #          → ものひろい → ? → 特性 → ものひろい → (explanation)
        # Detect EVERY such verified pair rather than stopping at the first.
        # Reject standalone descriptions and texts from lower page sections.
        hp_i = seek('HP', a_i + 1)
        end = min(len(lines), a_i + 65, hp_i if hp_i is not None else len(lines))
        for i in range(a_i + 1, end):
            word = lines[i].strip().replace('?', '').strip()
            if not (2 <= len(word) <= 16):
                continue
            if word in ('特性', 'とくせい', '特性とは', 'タイプ', '高さ', '重さ'):
                continue
            if re.search(r'[。！？、:：\d\s（）()]', word):
                continue
            following = [t.strip().replace('?', '').strip()
                         for t in lines[i+1:min(i+5, end)]]
            if word in following and word not in abilities:
                abilities.append(word)
    def following_value(label, regex):
        pos = seek(label)
        if pos is None:return None
        for word in lines[pos+1:pos+5]:
            if re.fullmatch(regex,word):return word
        return None
    category=following_value('分類',r'[^\s:：]{2,40}ポケモン')
    height=following_value('高さ',r'[0-9]+(?:\.[0-9]+)?m')
    weight=following_value('重さ',r'[0-9]+(?:\.[0-9]+)?kg')
    return {'types': types, 'abilities': abilities, 'url': url,
            'classification':category,'height':height,'weight':weight,
            'abilities_scope': 'official_zukan_displayed',
            'hidden_abilities_verified': False}


def get_official_profile_from_zukan(row, fetch):
    """Return official zukan data plus species-specific independently cited abilities.

    Verified five-species offline profiles are preferred for reproducibility;
    all other species use the existing official-zukan-only path.
    """
    url = official_zukan_url(row)
    if not url:
        return None
    exception = _PERMITTED_ABILITY_EXCEPTION.get(str(row['id']))
    if (exception and exception['name'] == row['name']
            and exception['official_zukan_url'] == url):
        # Type and displayed ability: official Pokédex. Hidden ability: explicitly
        # user-permitted secondary source, strictly limited to abilities.
        hidden = list(exception['hidden_abilities'])
        displayed = list(exception['official_displayed_abilities'])
        source_url = exception['hidden_ability_source_url']
        return {'types': list(exception['official_types']),
                'abilities': displayed + [v for v in hidden if v not in displayed],
                'hidden_abilities': hidden, 'hidden_source_urls': [source_url],
                'permitted_nonofficial_ability_urls': [source_url],
                'hidden_abilities_verified': True,
                'abilities_scope': 'official_pokedex_plus_user_permitted_ability_only',
                'url': url}
    evidence = _VERIFIED_HIDDEN.get(str(row['id']))
    if evidence and evidence['name'] == row['name'] and evidence['zukan_url'] == url:
        profile = {
            'types':list(evidence['types']),
            'abilities':list(evidence['displayed_abilities']),
            'url':url,
            'abilities_scope':'official_zukan_displayed',
            'hidden_abilities_verified':False,
        }
        return attach_official_hidden(profile,row)
    supplement = _VERIFIED_EXTRA.get(str(row['id']))
    if (supplement and supplement['name'] == row['name']
            and supplement['zukan_url'] == url):
        return attach_official_hidden({
            'types': list(supplement['types']),
            'abilities': list(supplement['displayed_abilities']),
            'url': url,
            'abilities_scope': 'official_zukan_displayed',
            'hidden_abilities_verified': False,
        }, row)
    latest = _OFFICIAL_PROFILE_OCT28.get(str(row['id']))
    if (latest and latest['name'] == row['name'] and latest['url'] == url):
        return attach_official_hidden({
            'types': list(latest['types']),
            'abilities': list(latest['displayed_abilities']),
            'url': url,
            'abilities_scope': 'official_zukan_displayed',
            'hidden_abilities_verified': False,
        }, row)
    known = OFFICIALLY_CHECKED.get(str(row['id']))
    if known and known['url'] == url:
        return attach_official_hidden(dict(known, abilities_scope='official_zukan_displayed',
                    hidden_abilities_verified=False),row)
    try:
        return attach_official_hidden(parse_official_zukan_html(fetch(url), url), row)
    except Exception:
        return None



def get_official_profile(row, fetch):
    """Strictly official: the Pokédex and individually sourced official hidden abilities.

    Hidden abilities without explicit official evidence remain unverified.
    """
    return get_official_profile_from_zukan(row, fetch)

def hint_points(step, informative_steps):
    """Starts at five; no point deduction for unavailable official hints."""
    return max(1, 5 - sum(i in informative_steps for i in range(1, step + 1)))
