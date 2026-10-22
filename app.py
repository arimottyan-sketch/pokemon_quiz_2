"""Unofficial staff self-study quiz. Stored official source sentences are never edited."""
import random
import requests
import streamlit as st
from quiz_engine import (read_db, national_number, display_quote, pokedex_records,
                         supplementary_records, REGIONS)
from staff_learning import (ALL_REGION, MODE_LABELS, DISPLAY_MODES, eligible_extra,
                            plan_session, pool_ids, region_for, make_history, progress_csv)

st.set_page_config(page_title='ポケモンをもっと知る｜スタッフ学習クイズ', page_icon='⚡', layout='centered')
st.markdown('''<style>
.block-container{max-width:920px;padding-top:1.7rem;padding-bottom:3rem}
[data-testid="stMetricValue"]{font-size:1.75rem}
@media(max-width:640px){.block-container{padding-top:.8rem;padding-left:.9rem;padding-right:.9rem}}
</style>''', unsafe_allow_html=True)

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
