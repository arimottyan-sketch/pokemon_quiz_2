"""Logic for an independent official-text Pokémon knowledge quiz.

No network operations. Official quotes are read from a committed JSON file only.
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import random
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data' / 'pokedex.json'
SUPPLEMENTS = ROOT / 'data' / 'supplements.json'
REGIONS = {'イッシュ': tuple(range(494, 650)), 'パルデア': tuple(range(906, 1026))}
TARGET_IDS = tuple(REGIONS['イッシュ'] + REGIONS['パルデア'])
OFFICIAL_DOMAIN = 'zukan.pokemon.co.jp'
SOURCE_TYPES = {'ゲーム内図鑑', 'ゲーム公式HP', 'アニメ公式X', 'ポケカ公式', '公式大会'}


def load_data(path=DATA):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('pokemon'), dict):
        raise ValueError('問題データの形式が不正です')
    for key, rec in data['pokemon'].items():
        if not key.isdecimal() or int(key) not in TARGET_IDS:
            raise ValueError(f'不正な番号キー: {key}')
        if int(rec.get('id', -1)) != int(key) or not isinstance(rec.get('name'), str) or not rec['name']:
            raise ValueError(f'ポケモン名・番号が不正: {key}')
        if not isinstance(rec.get('quotes'), list):
            raise ValueError(f'図鑑が未収録: {key}')
        for q in rec['quotes']:
            if q.get('kind') != 'ゲーム内図鑑' or not all(isinstance(q.get(k),str) and q[k] for k in ('text','url','source_title')):
                continue
            if q['url'] != f'https://zukan.pokemon.co.jp/detail/{int(key):04d}':
                raise ValueError(f'図鑑公式URLの番号不一致: {key}')
    return data


def dex_entries(row):
    """All available source-attributed game Pokédex quotes. No supplements."""
    if not row or row.get('data_status') not in {'official_html_collected', 'official_index_excerpt_reviewed'}:
        return []
    return [q for q in row.get('quotes', []) if q.get('kind') == 'ゲーム内図鑑'
            and q.get('review_status') in {'official_html_collected', 'official_index_excerpt_reviewed'}
            and all(isinstance(q.get(k),str) and q[k] for k in ('text', 'url', 'source_title'))]


def coverage(data, region):
    ids = TARGET_IDS if region == '両地方' else REGIONS[region]
    present = [pid for pid in ids if dex_entries(data['pokemon'].get(str(pid)))]
    missing = [pid for pid in ids if pid not in present]
    fetched = [pid for pid in present if data['pokemon'][str(pid)].get('official_fetch')]
    return {'target': len(ids), 'present': present, 'missing': missing, 'fetched': fetched}


def eligible_supplement(q, today=None):
    """Never treat recent cards as timeless; 3-year policy. Official sources only."""
    if q.get('kind') not in SOURCE_TYPES - {'ゲーム内図鑑'}:
        return False
    url = q.get('url','')
    parsed = urlsplit(url)
    allowed_domains = {'www.pokemon.co.jp', 'www.pokemon-card.com', 'www.tv-tokyo.co.jp'}
    if q['kind'] == 'アニメ公式X':
        account = str(q.get('verified_account','')).lstrip('@').lower()
        proof = urlsplit(q.get('account_proof_url',''))
        if parsed.hostname not in {'x.com', 'twitter.com'} or proof.hostname not in allowed_domains or not account or not parsed.path.lower().startswith(f'/{account}/status/'):
            return False
    elif parsed.scheme != 'https' or parsed.hostname not in allowed_domains:
        return False
    if parsed.scheme != 'https' or parsed.username or parsed.password:
        return False
    if not q.get('text') or not q.get('source_title'):
        return False
    if q['kind'] not in {'ポケカ公式', '公式大会'}:
        return True
    date_key = 'first_release_on' if q['kind'] == 'ポケカ公式' else 'event_date'
    try:
        event_day = date.fromisoformat(q[date_key]); current = today or date.today()
        try:
            cutoff = current.replace(year=current.year-3)
        except ValueError:  # 2月29日に対応
            cutoff = current.replace(year=current.year-3, day=28)
    except (KeyError, ValueError, TypeError):
        return False
    return cutoff <= event_day <= current


def load_supplements(path=SUPPLEMENTS):
    if not Path(path).is_file():
        return {}
    obj = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(obj, dict):
        raise ValueError('補足データの形式が不正です')
    for key, recs in obj.items():
        if not key.isdigit() or int(key) not in TARGET_IDS or not isinstance(recs,list):
            raise ValueError(f'補足データの形式が不正: {key}')
    return obj


def make_session(data, region, mode, count, *, preview=False, seed=None, target_ids=None):
    """Return all requested targets exactly once. Never silently skip a missing entry.

    mode: 'who' (description -> species), 'which' (species -> description), 'mix'.
    When all of a species' texts say its name, switch THAT question to 'which'
    so no original text has to be altered or the species omitted.
    """
    if mode not in {'who', 'which', 'mix'}:
        raise ValueError('問題形式が不正')
    ids = list(target_ids if target_ids is not None else TARGET_IDS if region == '両地方' else REGIONS[region])
    pool = {pid: dex_entries(data['pokemon'].get(str(pid))) for pid in (TARGET_IDS if region == '両地方' else REGIONS[region])}
    missing = [pid for pid in ids if not pool.get(pid)]
    if missing:
        raise ValueError('図鑑が未収録のポケモンがあります: ' + ', '.join(map(str,missing[:20])))
    if sum(bool(v) for v in pool.values()) < 4:
        raise ValueError('四択には図鑑原文を持つ4匹以上が必要です')
    rng = random.Random(seed)
    rng.shuffle(ids)
    if isinstance(count,int) and count > 0:
        ids = ids[:min(count,len(ids))]
    questions = []
    for pid in ids:
        name = data['pokemon'][str(pid)]['name']
        samples = pool[pid]
        no_name = [q for q in samples if name not in q['text']]
        actual_mode = ('who' if mode == 'mix' and rng.random()<0.5 else 'which' if mode == 'mix' else mode)
        if actual_mode == 'who' and not no_name:
            actual_mode = 'which'
        right = rng.choice(no_name if actual_mode == 'who' else samples)
        others = list(pool)
        rng.shuffle(others)
        opts = [{'id': pid, 'text': right['text'], 'quote': right}]
        used = {right['text']}
        for oid in others:
            if oid == pid or not pool[oid]:
                continue
            ok = [q for q in pool[oid] if q['text'] not in used]
            if not ok:
                continue
            q = rng.choice(ok)
            opts.append({'id':oid, 'text':q['text'], 'quote':q})
            used.add(q['text'])
            if len(opts) == 4:
                break
        if len(opts) != 4:
            raise ValueError(f'No.{pid:04d}: 重複しない四択を生成できません')
        rng.shuffle(opts)
        questions.append({'pokemon_id':pid, 'name':name, 'mode':actual_mode,
                          'quote':right, 'choices':opts,
                          'correct_index':next(j for j,x in enumerate(opts) if x['id']==pid)})
    return questions
