"""One-time official Pokédex importer for GitHub Actions; never used by the Streamlit app.

Reads ONLY the JSON embedded in https://zukan.pokemon.co.jp/detail/XXXX.
No rewriting, summaries, PokeAPI flavor-text substitution, or silent omissions.
Once fetched, entries are stored in data/official_quotes.json.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

from quiz_core import REGIONS, load_data

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / 'data' / 'pokedex.json'
STATUS_PATH = BASE / 'data' / 'collection_status.json'
TEXT_KEY = re.compile(r'text_(\d+)\Z')
WORK_TITLE = re.compile(r'\s*（『([^』]+)』より）\s*\Z')
OFFICIAL = 'https://zukan.pokemon.co.jp/detail/{:04d}'
TIMEOUT = 20


def parse_official_page(html: str, pokemon_id: int, *, fetched_on: str):
    """Extract native official JSON. Reject ambiguous/mismatched pages instead of guessing."""
    soup = BeautifulSoup(html, 'html.parser')
    script = soup.find('script', id='json-data', type='application/json')
    if script is None:
        raise ValueError('公式HTMLに script#json-data がありません')
    # BeautifulSoup's .get_text() may be empty for <script>; use .string.
    raw_json = script.string
    if not raw_json:
        raise ValueError('公式HTMLの埋め込みJSONが空欄です')
    root = json.loads(str(raw_json))
    pokemon = root['pokemon']
    if int(pokemon['no']) != pokemon_id or int(pokemon.get('sub', 0)) != 0:
        raise ValueError('公式HTMLの図鑑番号またはフォルムが一致しません')
    name = pokemon['name']
    if not isinstance(name, str) or not name.strip():
        raise ValueError('公式のポケモン名がありません')
    url = OFFICIAL.format(pokemon_id)
    quotes = []
    seen = set()
    text_keys = sorted((k for k in pokemon if TEXT_KEY.fullmatch(k)),
                       key=lambda k: int(TEXT_KEY.fullmatch(k).group(1)))
    for key in text_keys:
        original = pokemon[key]
        if not isinstance(original, str) or not original.strip():
            continue
        attribution = WORK_TITLE.search(original)
        if attribution is None:
            raise ValueError(f'{key}: 作品名の出典表示を分離できません（推測補完はしません）')
        # Preserve literal text content. Only remove the website's title attribution.
        body = original[:attribution.start()]
        if not body.strip() or body in seen:
            continue
        seen.add(body)
        quotes.append({
            'kind': 'ゲーム内図鑑',
            'source_title': f"『{attribution.group(1)}』図鑑",
            'url': url,
            'text': body,
            'original_with_attribution': original,
            'source_field': key,
            'source_sha256': hashlib.sha256(original.encode('utf-8')).hexdigest(),
            'verified_on': fetched_on,
            'review_status': 'official_html_collected',
        })
    if not quotes:
        raise ValueError('公式ページのゲーム内図鑑原文がありません')
    return {
        'id': pokemon_id,
        'name': name,
        'data_status': 'official_html_collected',
        'image_url': pokemon.get('image_m') if str(pokemon.get('image_m','')).startswith('https://zukan.pokemon.co.jp/') else '',
        'quotes': quotes,
        'official_fetch': {
            'source': '公式ポケモンずかん HTML内 json-data',
            'url': url,
            'fetched_on': fetched_on,
            'verified_fields': [q['source_field'] for q in quotes],
        }
    }


def retrieve_one(session: requests.Session, pokemon_id: int, timeout: int):
    url = OFFICIAL.format(pokemon_id)
    response = session.get(url, timeout=timeout, allow_redirects=False, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; PersonalPokemonQuizDataCheck/1.0)'
    })
    response.raise_for_status()
    if response.is_redirect or response.is_permanent_redirect:
        raise ValueError('公式URLがリダイレクトを返しました')
    return parse_official_page(response.text, pokemon_id,
                               fetched_on=datetime.now(timezone.utc).date().isoformat())


def save_atomically(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def is_fetched(row):
    if not isinstance(row, dict) or not row.get('official_fetch'):
        return False
    if row['official_fetch'].get('url') != OFFICIAL.format(row['id']):
        return False
    qs = [q for q in row.get('quotes', []) if q.get('kind') == 'ゲーム内図鑑']
    if not qs:
        return False
    for q in qs:
        original = q.get('original_with_attribution')
        if not isinstance(original, str):
            return False
        match = WORK_TITLE.search(original)
        if match is None or original[:match.start()] != q.get('text'):
            return False
        if hashlib.sha256(original.encode('utf-8')).hexdigest() != q.get('source_sha256'):
            return False
        if q.get('url') != OFFICIAL.format(row['id']):
            return False
    return True


def collect(*, session=None, ids=None, delay=0.55, retries=2, refresh_all=False,
            save=True, timeout=TIMEOUT):
    if session is None:
        session = requests.Session()
    ids = list(ids if ids is not None else [*REGIONS['イッシュ'], *REGIONS['パルデア']])
    db = load_data(DB_PATH)
    failures = {}
    attempts = 0
    for i, pid in enumerate(ids, 1):
        old = db['pokemon'].get(str(pid))
        if old and is_fetched(old) and not refresh_all:
            continue
        attempts += 1
        try:
            new = None
            last_error = ''
            for attempt in range(retries + 1):
                try:
                    new = retrieve_one(session, pid, timeout)
                    break
                except (requests.RequestException, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    last_error = f'{type(exc).__name__}: {exc}'
                    if attempt < retries:
                        time.sleep(delay * (attempt + 1))
            if new is None:
                failures[str(pid)] = last_error
                continue
            # Preserve already registered SUPPLEMENTARY official-site/card facts;
            # never use them as a substitute for an actual game Pokédex entry.
            if old:
                old_extra = [q for q in old.get('quotes', []) if q.get('kind') != 'ゲーム内図鑑']
                new['quotes'].extend(old_extra)
            db['pokemon'][str(pid)] = new
        finally:
            if save and i % 20 == 0:
                save_atomically(DB_PATH, db)
            if delay > 0:
                time.sleep(delay)
        if i % 25 == 0:
            print(f'公式取得試行 {i}/{len(ids)}（No.{pid:04d}）、失敗 {len(failures)}', flush=True)
    if db.get('schema_version') != 1:
        raise ValueError('データ形式が不正')
    full_ids = [*REGIONS['イッシュ'], *REGIONS['パルデア']]
    missing = [pid for pid in full_ids if not is_fetched(db['pokemon'].get(str(pid)))]
    status = {
        'all_target_count': len(full_ids), 'fetched_from_official_count': len(full_ids)-len(missing),
        'missing_ids': missing, 'errors': failures, 'attempted_this_run': attempts,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    if save:
        save_atomically(DB_PATH, db)
        save_atomically(STATUS_PATH, status)
    return db, status


def main(argv=None):
    ap = argparse.ArgumentParser(description='公式ポケモンずかんから276匹の原文を一度だけ取得・固定保存')
    ap.add_argument('--refresh-all', action='store_true', help='保存済み分も公式から再取得')
    ap.add_argument('--delay', type=float, default=0.55)
    ap.add_argument('--timeout', type=int, default=TIMEOUT)
    ap.add_argument('--retries', type=int, default=2)
    args = ap.parse_args(argv)
    try:
        _, status = collect(delay=args.delay, timeout=args.timeout,
                            retries=args.retries, refresh_all=args.refresh_all)
    except Exception as e:
        print(f'データ収集が異常終了しました：{e}', file=sys.stderr)
        return 1
    print(f"公式サイトから取得済み：{status['fetched_from_official_count']}/276匹")
    if status['missing_ids']:
        print(f"未取得番号：{status['missing_ids']}")
        return 2
    print('全276匹分の公式原文を取得し、GitHubへ登録できる形式のJSONに保存しました。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
