"""Unova / Paldea official-text quiz, offline questions with optional artwork."""
import random
import requests
import streamlit as st
from pathlib import Path
from quiz_engine import *

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
        st.warning('この姿の画像を取得できません。姿当て系は画像を表示できる環境で利用してください。通常の姿では代用しません。')


def source(rec):
    if rec.get('quiz_attribution_scope')=='作品内・個体に関する記述':
        st.caption('※公式作品内の描写・伝承。種全体の一般的な生態を断定するものではありません。')
    if rec.get('quiz_approved') is False:
        st.caption('※出題対象外の資料記録（参考閲覧のみ）。')
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
        st.markdown('#### この公式の文章は、どのポケモンについての記述？')
        if kind == 'extra_description':
            source_rec=q['quotes'][pid]
            scope=source_rec.get('source_scope') or source_rec.get('quiz_attribution_scope','公式資料の説明')
            scope=display_quote(scope,pid,db)
            st.caption(f'適用範囲：{scope}。作品内の出来事や伝承は種全体の習性とは限りません。')
        st.write(display_quote(q['quotes'][pid]['text'], pid, db))
        st.caption('※正解名が文章に含まれる場合のみ「？？？」に置換。解答後は保存された原文を表示します。')

    if kind == 'typed':
        with st.form(f'write_{n}'):
            answer_text = st.text_input('カタカナで名前を入力', disabled=answered, autocomplete='off')
            submit = st.form_submit_button('回答する', disabled=answered, type='primary')
        if submit:
            # No aliases silently accepted: spelling practice is exact.
            chosen = pid if answer_text.strip() == row['name'] else None
            commit(chosen)
    elif kind in ('description', 'extra_description') and not q.get('force_text_choices'):
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


st.title('ポケモン公式原文クイズ｜イッシュ・パルデア')
st.caption('イッシュ156種・パルデア120種＋指定リージョンフォーム4枠。登録した公式文章は保存し、出題時のみ正解名を伏字化。')
page = st.radio('画面', ['クイズ', 'ポケモン情報', '使い方'], horizontal=True,
                label_visibility='collapsed')

if page == 'クイズ':
    st.caption('図鑑405件＋図鑑外の採用可能情報を掲載。図鑑外は1種1問に制限せず、原文抜粋1件ずつ出題します。全件の逐字再検証は未了。')
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
            st.caption(f'出題対象：{extra_record_count(db,region)}件の図鑑外情報（種・すがたは{len(available)}枠）' if mode.startswith('extra_') else f'この設定での出題対象：{len(available)}種類・すがた')
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
- **図鑑外の公式情報**：原資料631件を保持し、条件を満たした原文抜粋を1件ずつ問題化。「図鑑外ミックス」を選べば採用した全情報に取り組めます。不適切候補は監査CSVに理由を記録しました。
- **作品個体の記述**：作品内・個体の出来事は種全体に当てはまる生態と混同しません。メガシンカ後の説明を普通のすがたの画像で出すことも避けます。
- **回答履歴**：結果画面からCSVを保存できます。
- **未完了の検証**：過去の図鑑登録文章405件すべてを2026-10-23に再照合したわけではありません。公式URLを解答後に示します。
- **画像**：PokeAPI提供のイラストURLを表示のみに利用。クイズ文章の情報源には使用しません。画像取得に失敗したら通常のすがたへ代用しません。
''')
