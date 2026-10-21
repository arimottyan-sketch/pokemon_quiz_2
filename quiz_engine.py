"""GitHubに固定保存した公式原文だけで、ゲーム内図鑑最優先の四択を生成する。

出題にゲーム公式図鑑以外は使わない。公式HP・アニメ・ポケカは解答後の補足に限定。
カード/大会は元カードの初登場日/大会開催日が最近3年以内のもののみ表示する。
ここで実施するのは形式と日付の検査であり、URL先との原文一致の証明ではない。
"""
import json
import random
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

REGIONS = {
    'イッシュ': list(range(494, 650)),
    'パルデア': list(range(906, 1026)),
}
APPROVED_HOSTS = {'zukan.pokemon.co.jp', 'www.pokemon.co.jp', 'www.pokemon-card.com', 'www.tv-tokyo.co.jp'}
SOURCE_KINDS = {'ゲーム内図鑑', 'ゲーム公式HP', 'ポケカ公式', 'アニメ公式', '大会公式', '公式図鑑プロフィール', 'ゲーム内図鑑の補足'}
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
        try:
            pid = int(key)
        except ValueError:
            raise ValueError(f'番号キーが不正: {key}') from None
        if str(pid) != key or not any(pid in ids for ids in REGIONS.values()):
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
            if '…' in rec['text'] or '（略）' in rec['text']:
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
    return sorted(pid for pid in REGIONS[region] if not pokedex_records(data['pokemon'].get(
        str(pid), {'quotes': []})))


def make_questions(data, region, mode, ids=None, seed=None):
    """picture(画像→図鑑原文) / description(図鑑原文→名前)

    正答とすべての誤答は必ずゲーム内図鑑。補足資料を選択肢に使用しない。
    """
    if mode not in ('picture', 'description'):
        raise ValueError('不正な問題形式')
    target = list(ids) if ids is not None else list(REGIONS[region])
    region_pool = {pid: pokedex_records(data['pokemon'][str(pid)])
                   for pid in REGIONS[region] if str(pid) in data['pokemon']
                   and pokedex_records(data['pokemon'][str(pid)])}
    absent = [pid for pid in target if pid not in region_pool]
    if absent:
        raise ValueError(f'ゲーム内図鑑がないポケモンがいます: {absent[:12]} (計{len(absent)}匹)')
    if len(region_pool) < 4:
        raise ValueError('四択作成に必要なゲーム内図鑑が4匹分ありません')
    rng = random.Random(seed)
    rng.shuffle(target)
    questions = []
    for pid in target:
        answer = rng.choice(region_pool[pid])
        # 完全同文の図鑑文章は選択肢に含めない（誤答の二重正解を防止）。
        candidate_ids = [x for x in region_pool if x != pid and
                         any(q['text'] != answer['text'] for q in region_pool[x])]
        if len(candidate_ids) < 3:
            raise ValueError('重複しない図鑑説明の選択肢を3件作れません')
        rng.shuffle(candidate_ids)
        other_ids = []
        choice_quotes = {pid: answer}
        used = {answer['text']}
        for other in candidate_ids:
            quote_candidates = [q for q in region_pool[other] if q['text'] not in used]
            if not quote_candidates:
                continue
            chosen = rng.choice(quote_candidates)
            used.add(chosen['text'])
            other_ids.append(other)
            choice_quotes[other] = chosen
            if len(other_ids) == 3:
                break
        if len(other_ids) != 3:
            raise ValueError('重複しない図鑑説明の選択肢を3件作れません')
        choices = [pid, *other_ids]
        rng.shuffle(choices)
        questions.append({'id': pid, 'answer': pid, 'choices': choices,
                          'quotes': choice_quotes, 'mode': mode})
    return questions
