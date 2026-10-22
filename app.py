"""Unofficial staff self-study quiz. Stored official source sentences are never edited."""
import random
import requests
import streamlit as st

# Stable, bundled quiz engine; no quiz_engine.py / staff_learning.py dependency.
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


def make_questions(data, region, mode, ids=None, seed=None):
    """picture(画像→図鑑原文) / description(図鑑原文→名前)

    正答とすべての誤答は必ずゲーム内図鑑。補足資料を選択肢に使用しない。
    """
    if mode not in ('picture', 'description', 'identification', 'extra_description'):
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
        if mode == 'extra_description':
            # Only verified, non-card supplementary records. Cards and tournaments
            # remain in the post-answer source panel, never used as quiz prompts.
            extras = [q for q in supplementary_records(data['pokemon'][str(pid)])
                      if q['kind'] in ('ゲーム公式HP', 'アニメ公式', 'ゲーム内図鑑の補足', '公式図鑑プロフィール', '公式グッズ紹介')]
            if not extras:
                raise ValueError(f'公式トリビア原文がありません: {pid}')
            answer = rng.choice(extras)
        else:
            answer = rng.choice(region_pool[pid])
        if mode in ('identification', 'extra_description'):
            # No distractor text is shown, so avoid only an identical species ID.
            candidates = [x for x in region_pool if x != pid]
            rng.shuffle(candidates)
            choices = [pid, *candidates[:3]]
            rng.shuffle(choices)
            questions.append({'id': pid, 'answer': pid, 'choices': choices,
                              'quotes': {pid: answer}, 'mode': mode})
            continue
        # Picture -> four distinct Pokedex descriptions.
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


st.set_page_config(page_title='ポケモンをもっと知る｜スタッフ学習クイズ', page_icon='⚡', layout='centered')
# GitHub's browser upload may reject .streamlit/: keep the shared color palette in
# a regular file and apply it to the page without any dot-prefixed upload path.
from pathlib import Path
_THEME_PATH = Path(__file__).with_name('staff_theme.css')
if _THEME_PATH.is_file():
    st.markdown('<style>\n' + _THEME_PATH.read_text(encoding='utf-8') + '\n</style>',
                unsafe_allow_html=True)

NAME_MODE = '名前入力（上級）'
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
    st.caption('確認するポイント：姿と名前、公式文に書かれた特徴を結び付けて覚えましょう。')


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
    elif kind == 'picture':
        st.markdown('#### このポケモンに当てはまる図鑑説明を選んでください')
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
            if kind == 'picture':
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
        if kind == 'picture':
            with st.expander('他の選択肢の出典'):
                for x in q['choices']:
                    if x != pid:
                        st.markdown(f"**{db['pokemon'][str(x)]['name']}**")
                        source(q['quotes'][x])
        if st.button('次の問題へ →',type='primary',use_container_width=True):
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
    st.header('今回の学習結果')
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
        st.download_button('学習履歴をCSVで保存', data=progress_csv(st.session_state.history,db).encode('utf-8'),
                           file_name='pokemon_staff_quiz_history.csv',mime='text/csv')
        st.caption('学習履歴はこのブラウザのセッション中のみ保持されます。端末を閉じる前にCSVで保存できます。')
    if st.button('新しいクイズを始める'):
        clear_question_only()
        st.rerun()


st.title('⚡ ポケモンをもっと知る')
st.caption('イッシュ・パルデア｜ポケモンセンタースタッフ向け自主学習クイズ（非公式）')
page = st.radio('画面', ['クイズで覚える','ポケモンを調べる','学習の使い方'], horizontal=True,
                label_visibility='collapsed')

if page == 'クイズで覚える':
    if st.session_state.specs is None:
        st.markdown('**名前と姿を見分ける → 公式の文章で特徴を知る → 間違いを復習する**')
        with st.form('quiz_options'):
            region = st.selectbox('出題する地方', [ALL_REGION,'イッシュ','パルデア'], index=0)
            options = list(MODE_LABELS.values()) + [NAME_MODE]
            mode_label = st.selectbox('学習メニュー', options, index=0)
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
            begin = st.form_submit_button('学習を始める', type='primary', disabled=not available,
                                          use_container_width=True)
        if begin:
            start(region,mode,count, review_ids=marked if restrict else None)
        st.info('おすすめ：最初は「バランスよく」10問。短時間で姿・名前・特徴を繰り返せます。')
    elif st.session_state.finished or st.session_state.idx >= len(st.session_state.specs):
        show_finish()
    else:
        show_question(st.session_state.specs[st.session_state.idx])
        st.caption('問題や画像に不具合がある場合も、公式原文を書き換えず出典ページで確認してください。')

elif page == 'ポケモンを調べる':
    st.subheader('公式の情報からポケモンを調べる')
    st.caption('接客前の確認や、答えられなかったポケモンのおさらいに。')
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
        st.caption(f"全国図鑑 No.{national_number(selected):04d}｜{region_for(selection)}の学習対象")
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
            if st.button('この子を1問練習',use_container_width=True):
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
    st.subheader('スタッフ研修としての使い方')
    st.markdown('''
**① 姿と名前を覚える**  — 「姿を見て名前を選ぶ」で商品や写真のポケモンを見分ける練習をします。

**② 特徴を覚える**  — 「図鑑説明から名前」「姿から図鑑説明」で、名前だけでなくそのポケモンの特徴も結び付けます。

**③ 話題を広げる**  — 「公式トリビア」で公式HPやアニメ紹介などの文章に触れます。アニメに登場した特定の個体の話は、種族全体の設定と混同しないよう出典を見ます。

**④ 苦手を復習する**  — 間違えた種類・すがたがセッション中の復習対象になり、正解しても残したいものは☆に登録できます。

**⑤ 調べてから伝える**  — 「ポケモンを調べる」で公式の文章と掲載元を見て、接客時に伝えたい特徴を確認します。
''')
    st.warning('このアプリは公式運営・会社の研修認定ツールではありません。店舗在庫、商品価格、配布物、最新イベントの情報を保証しません。')
    st.caption('原文データは改変せず保存していますが、既存のすべての文章の公式ページとの全面再照合をこの改修で行ったわけではありません。')
    st.markdown('[ポケモンセンター公式サイト ↗](https://shop.pokemon.co.jp/)')
    st.markdown('[ポケモン公式図鑑 ↗](https://zukan.pokemon.co.jp/)')
