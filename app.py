"""Pokémon quiz. Static official quotes; no website scraping at app runtime."""
import random

import requests
import streamlit as st
import streamlit.components.v1 as components

from quiz_engine import (REGIONS as KNOWLEDGE_REGIONS, read_db, missing_ids,
                         make_questions, pokedex_records, supplementary_records,
                         three_year_cutoff)

ALL_REGIONS = {
    'カントー (1–151)': range(1, 152),
    'ジョウト (152–251)': range(152, 252),
    'ホウエン (252–386)': range(252, 387),
    'シンオウ (387–493)': range(387, 494),
    'イッシュ (494–649)': range(494, 650),
    'カロス (650–721)': range(650, 722),
    'アローラ (722–809)': range(722, 810),
    'ガラル (810–898)': range(810, 899),
    'ヒスイ (899–905)': range(899, 906),
    'パルデア (906–1025)': range(906, 1026),
}
TYPE_MAP = {
    'normal': 'ノーマル', 'fire': 'ほのお', 'water': 'みず', 'grass': 'くさ',
    'electric': 'でんき', 'ice': 'こおり', 'fighting': 'かくとう', 'poison': 'どく',
    'ground': 'じめん', 'flying': 'ひこう', 'psychic': 'エスパー', 'bug': 'むし',
    'rock': 'いわ', 'ghost': 'ゴースト', 'dragon': 'ドラゴン', 'dark': 'あく',
    'steel': 'はがね', 'fairy': 'フェアリー',
}
SPECIALS = {
    'ピカチュウ': '10まんボルトだ！', 'トリトドン': 'ぽわ～ぐちょぐちょ',
    'ミカルゲ': 'おんみょ～ん', 'ポッチャマ': 'ぽちゃぽっちゃ！',
    'ノココッチ': 'にげあしドロー', 'ヘラクロス': 'むし！',
    'ドラパルト': 'ファントムダイブ！', 'サマヨール': 'カースドボム！',
    'ヨノワール': 'カースドボム！', 'マシマシラ': 'アドレナブレイン！',
'スボミー': 'むずむずかふん！',
    'ビクティニ': '無限のパワー！', 'ゲッコウガ': 'へんげんじざい！',
    'ニャスパー': 'もこお！', 'ミミッキュ': 'ラス１なんやかんやできるミミッキュで',
    'パモ': '床の隙間の汚れwatching．かわいいかわいいね',
    'パルキア': 'パルキアのばかやろー！',
}
NAME_MODE = '名前当て（従来）'
PICTURE_MODE = '公式知識四択（画像→説明文）'
TEXT_MODE = '公式知識四択（説明文→名前）'


@st.cache_data(ttl=86400, show_spinner=False)
def get_name_and_art(pid):
    """Retain the original image/name quiz's PokeAPI dependency.
    Official quote text is NEVER obtained through the API.
    """
    try:
        pok = requests.get(f'https://pokeapi.co/api/v2/pokemon/{pid}', timeout=15)
        pok.raise_for_status()
        a = pok.json()
        sp = requests.get(f'https://pokeapi.co/api/v2/pokemon-species/{pid}', timeout=15)
        sp.raise_for_status()
        b = sp.json()
        name = next((n['name'] for lang in ('ja-Hrkt', 'ja-hrkt', 'ja')
                     for n in b['names'] if n['language']['name'] == lang), None)
        art = (a.get('sprites', {}).get('other', {}).get('official-artwork') or {}).get('front_default')
        art = art or a.get('sprites', {}).get('front_default')
        types = [TYPE_MAP.get(t['type']['name'], t['type']['name']) for t in a.get('types', [])]
        return name, art, types
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None, None, []


def begin(ids, mode, region_key=None, review=False, preview=False):
    specs = []
    if mode == NAME_MODE:
        random.shuffle(ids)
        specs = [{'id': p} for p in ids]
    else:
        specs = make_questions(db, region_key,
                               'picture' if mode == PICTURE_MODE else 'description',
                               ids=ids)
    if not review:
        st.session_state.missed = []
    st.session_state.specs = specs
    st.session_state.index = 0
    st.session_state.score = 0
    st.session_state.result = None
    st.session_state.finished = False
    st.session_state.review = review
    st.session_state.mode = mode
    st.session_state.region_key = region_key
    st.session_state.preview = preview


def show_source(rec):
    st.caption(f"出典：{rec['source_title']}（{rec['kind']}）")
    st.markdown(f"[公式の出典ページを開く]({rec['url']})")


def show_extra_for_name(pid):
    data = db['pokemon'].get(str(pid))
    if not data:
        st.caption('このポケモンの公式原文解説は、固定データへの収録がまだ完了していません。')
        return
    # 解説は「ゲーム内図鑑」→「補足」の順を固定。カードは直近3年のみ。
    for r in pokedex_records(data):
        st.markdown(f"**ゲーム内図鑑：** {r['text']}")
        show_source(r)
    extras = supplementary_records(data)
    if extras:
        with st.expander('その他の公式情報（補足）'):
            for r in extras:
                st.write(r['text'])
                show_source(r)


def end_now():
    if st.session_state.review:
        idx = st.session_state.index
        start = idx if st.session_state.result is None else idx + 1
        for spec in st.session_state.specs[start:]:
            if spec['id'] not in st.session_state.missed:
                st.session_state.missed.append(spec['id'])
    st.session_state.finished = True
    st.rerun()


def record(ok, msg, pid):
    st.session_state.result = (ok, msg)
    if ok:
        st.session_state.score += 1
        if st.session_state.review and pid in st.session_state.missed:
            st.session_state.missed.remove(pid)
    elif pid not in st.session_state.missed:
        st.session_state.missed.append(pid)


def next_on_enter():
    components.html('''<script>
    (function(){
      if (/iPhone|iPad|iPod|Android|Mobile/i.test(navigator.userAgent)) return;
      const d = window.parent.document;
      if (d.__officialPokemonQuizNextInstalled) return;
      d.__officialPokemonQuizNextInstalled = true;
      let t = 0;
      d.addEventListener('keydown', function(e){
        if(e.key !== 'Enter' || e.repeat || e.shiftKey || e.ctrlKey || e.metaKey) return;
        const b = Array.from(d.querySelectorAll('button')).find(x => x.innerText.trim() === '次の問題へ');
        if(!b || Date.now() - t < 500) return;
        t = Date.now(); e.preventDefault(); b.click();
      });
    })();
    </script>''', height=0)


st.set_page_config(page_title='ポケモンクイズ', page_icon='⚡')
st.title('ポケモンクイズ')
st.caption('公式出典付き固定データを使用。全件の公式原文との再照合は未完了です。')
try:
    db = read_db()
except (OSError, ValueError) as exc:
    st.error(f'固定問題データを読み込めません。GitHub の data/official_quotes.json を確認してください。詳細: {exc}')
    st.stop()

if 'specs' not in st.session_state:
    region_name = st.selectbox('地方を選ぶ', list(ALL_REGIONS), index=4)
    mode = st.radio('クイズ形式', [NAME_MODE, PICTURE_MODE, TEXT_MODE])
    num = st.selectbox('問題数', [10, 20, 30, 50, '全問'], index=1)
    region_key = 'イッシュ' if region_name.startswith('イッシュ') else (
        'パルデア' if region_name.startswith('パルデア') else None)
    if mode == NAME_MODE:
        st.caption('名前当ての名前・画像・タイプ取得には、元アプリと同じPokeAPIを使用します。')
        if st.button('開始', type='primary'):
            ids = list(ALL_REGIONS[region_name])
            if isinstance(num, int):
                ids = random.sample(ids, min(num, len(ids)))
            begin(ids, mode)
            st.rerun()
    elif region_key is None:
        st.warning('公式知識四択は現在、イッシュ・パルデア用のデータ形式です。')
    else:
        missing = missing_ids(db, region_key)
        n = len(KNOWLEDGE_REGIONS[region_key])
        st.write(f'**ゲーム内図鑑の収録：{n-len(missing)} / {n}匹**')
        if missing:
            st.warning('全匹のゲーム内図鑑原文がまだ揃っていません。未収録のポケモンを除外せず、全種モードを停止しています。')
            with st.expander('未収録の図鑑番号'):
                st.write('、'.join(f'{p:04d}' for p in missing))
            st.caption('ゲーム内図鑑が必須です。公式HP・アニメ・ポケカは回答後の補足だけに使用。GitHub上の data/official_quotes.json を更新すると反映されます。')
            preview = st.checkbox('開発用：収録済みの問題だけ試す（全種対応の完成版ではありません）')
        else:
            preview = False
        available = [p for p in KNOWLEDGE_REGIONS[region_key]
                     if str(p) in db['pokemon'] and pokedex_records(db['pokemon'][str(p)])]
        can_begin = (not missing or (preview and len(available) >= 4))
        st.caption(f'カード・大会情報は過去約3年（{three_year_cutoff().isoformat()}以降）に限定。図鑑情報には期限を設けません。')
        if st.button('クイズ開始' if not preview else '試作問題をプレイ',
                     disabled=not can_begin, type='primary'):
            ids = available if preview else list(KNOWLEDGE_REGIONS[region_key])
            if isinstance(num, int):
                ids = random.sample(ids, min(num, len(ids)))
            begin(ids, mode, region_key, preview=preview)
            st.rerun()

else:
    specs = st.session_state.specs
    i = st.session_state.index
    if i >= len(specs):
        st.session_state.finished = True
    if not st.session_state.finished:
        spec = specs[i]
        pid = spec['id']
        mode = st.session_state.mode
        st.markdown(f'### 問題 {i+1} / {len(specs)}')
        st.write(f'正解数：{st.session_state.score} / {len(specs)}')
        if st.session_state.preview:
            st.caption('開発用試作問題：全種完成版ではありません')
        if mode == NAME_MODE:
            name, picture, types = get_name_and_art(pid)
            if not name:
                st.error(f'No.{pid:04d} の名前データを取得できませんでした。通信状態を確認し、再読み込みしてください。別のポケモンには進まず、同じ問題に留まります。')
                st.stop()
            if picture:
                st.image(picture, width=300)
            with st.form(f'name_{i}'):
                ans = st.text_input('名前をカタカナで入力', key=f'input_{i}')
                submitted = st.form_submit_button('送信', disabled=st.session_state.result is not None)
                stopped = st.form_submit_button('途中終了')
            if submitted and st.session_state.result is None:
                if ans == name:
                    msg = 'そ～なんす！' if name == 'ソーナンス' else ('そ～なの！' if name == 'ソーナノ' else ('正解！ ' + SPECIALS.get(name, '')).strip())
                    record(True, msg, pid)
                else:
                    extra = ' いぬぬわん！' if name == 'ワンパチ' and ans in ('イヌヌワン', 'いぬぬわん') else ''
                    record(False, f'不正解！ 正解は {name}{extra}', pid)
        else:
            row = db['pokemon'][str(pid)]
            name = row['name']
            if mode == PICTURE_MODE:
                st.image(f'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{pid}.png', width=270)
                st.write(f'**No.{pid:04d} {name}** に該当するゲーム内図鑑の説明文を選んでください。')
                labels = [spec['quotes'][p]['text'] for p in spec['choices']]
            else:
                st.write('次のゲーム内図鑑の説明文に該当するポケモンを選んでください。')
                st.markdown(f"**{spec['quotes'][pid]['text']}**")
                labels = [db['pokemon'][str(p)]['name'] for p in spec['choices']]
            with st.form(f'four_{i}'):
                selection = st.radio('選択肢', list(range(4)), format_func=lambda n: labels[n], key=f'answer_{i}')
                submitted = st.form_submit_button('送信', disabled=st.session_state.result is not None)
                stopped = st.form_submit_button('途中終了')
            if submitted and st.session_state.result is None:
                correct = spec['choices'][selection] == pid
                record(correct, '正解！' if correct else f'不正解！ 正解は {name}', pid)
        if stopped:
            end_now()
        if st.session_state.result is not None:
            ok, message = st.session_state.result
            (st.success if ok else st.error)(message)
            if mode == NAME_MODE:
                if types:
                    st.info(f"タイプ：{' / '.join(types)}")
                show_extra_for_name(pid)
            else:
                st.markdown('**ゲーム内図鑑（最優先）・出典**')
                st.write(f"**正解：{name}**")
                r = spec['quotes'][pid]
                st.write(r['text'])
                show_source(r)
                extras = supplementary_records(db['pokemon'][str(pid)])
                if extras:
                    with st.expander('その他の公式情報（追加知識）'):
                        for info in extras:
                            st.write(info['text'])
                            show_source(info)
                            if info['kind'] == 'ポケカ公式':
                                st.caption(f"カードの初登場日：{info['first_release_on']}。個別カードの情報であり、現行環境で強いことを示すものではありません。")
                            if info['kind'] == '大会公式':
                                st.caption(f"大会開催日：{info['event_date']}（当時の実績であり、現在の強さを保証しません）")
                if mode == PICTURE_MODE:
                    with st.expander('他の選択肢の出典'):
                        for other in spec['choices']:
                            if other == pid:
                                continue
                            st.write(f"**{db['pokemon'][str(other)]['name']}**")
                            show_source(spec['quotes'][other])
            next_on_enter()
            if st.button('次の問題へ'):
                st.session_state.index += 1
                st.session_state.result = None
                st.rerun()
    else:
        st.header('終了')
        st.write(f'今回のスコア：{st.session_state.score} / {len(specs)}')
        missed = st.session_state.get('missed', [])
        if missed:
            st.write(f'現在の復習対象：{len(missed)}問')
            if st.button('ミスだけ復習'):
                begin(missed.copy(), st.session_state.mode,
                      st.session_state.region_key, review=True,
                      preview=st.session_state.preview)
                st.rerun()
        else:
            st.success('すべてのミスをクリアしました！')
        if st.button('最初に戻る'):
            st.session_state.clear()
            st.rerun()
