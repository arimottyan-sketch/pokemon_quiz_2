"""独立した図鑑知識クイズ。問題文はGitHubに保存した公式資料だけを使用。"""
from __future__ import annotations

import html
import random

import streamlit as st

from quiz_core import (
    REGIONS, TARGET_IDS, coverage, dex_entries, eligible_supplement,
    load_data, load_supplements, make_session,
)

st.set_page_config(
    page_title='ポケモン生態クイズ | ずかんノート',
    page_icon='📖',
    layout='centered',
    initial_sidebar_state='collapsed',
)

st.markdown('''
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600;700;800&display=swap');
:root {--ink:#18373a; --mint:#176e70; --muted:#657b7c; --line:#dce8e5}
html, body, [class*="css"], .stApp {font-family: "Noto Sans JP", sans-serif;}
.stApp {background: linear-gradient(180deg,#edf5f2 0,#f8faf8 320px,#f8faf8 100%);}
.block-container {padding-top: 2.2rem !important;max-width:850px;padding-bottom:4rem !important;}
header[data-testid="stHeader"] {background:transparent}
[data-testid="stAppViewBlockContainer"] > div {gap:1rem;}
.stButton>button {min-height:3.0rem;border:1px solid #cddedb;border-radius:13px;
  background:white;color:#1d3d40;font-weight:700;box-shadow:0 2px 10px #254a420b;
  white-space:normal; height:auto; padding:14px 18px; transition: all 140ms ease;}
.stButton>button:not(:disabled):hover {border-color:#16817c;background:#eff8f5;color:#095b57;transform:translateY(-1px)}
.stButton>button[kind="primary"] {background:#0d6d6b;color:white;border-color:#0d6d6b;}
.stButton>button[kind="primary"]:hover{background:#095c5b;color:white;}
[data-testid="stRadio"] div[role="radiogroup"] {gap:12px;}
[data-testid="stRadio"] label {padding:5px 0}
[data-testid="stProgressBar"] div[role="progressbar"] > div {background:#14877e}
[data-testid="stMetric"] {background:white;border:1px solid #deebe8;border-radius:14px;padding:12px 16px;}
[data-testid="stMetricValue"] {font-size:1.6rem;}
[data-testid="stAlert"] {border-radius:14px;}
[data-testid="stImage"] img {max-height:235px; object-fit:contain;filter:drop-shadow(0 18px 14px #2749411f);}
.hero {border-radius:25px; background:linear-gradient(126deg,#103d46 0%,#125b60 58%,#167a76 100%);
    padding:35px 38px;color:#fff; position:relative;overflow:hidden; box-shadow:0 15px 30px #143f4424;}
.hero:after {content:'◓'; position:absolute;right:-13px;top:-70px;font-size:240px;color:#ffffff13;transform:rotate(27deg)}
.eyebrow {font-size:11px;letter-spacing:.21em;font-weight:800;color:#a8e2cf;margin-bottom:14px}
.hero h1 {font-size:clamp(27px,6vw,44px);font-weight:800;letter-spacing:.02em;line-height:1.3;margin:0 0 10px;color:#fff}
.hero p {font-size:14px;color:#d7f0ea;line-height:1.8;margin-bottom:0;max-width:480px}
.section-title {font-size:17px;font-weight:800;color:var(--ink);margin:18px 0 7px}
.note {color:#587576;font-size:13px;line-height:1.9;margin:4px 0 9px}
.question {padding:23px 26px;border-radius:19px;background:white;border:1px solid #d6e5e2;
 box-shadow:0 12px 30px #1c4d4111;margin:10px 0 18px}
.qcaption {font-size:12px;letter-spacing:.13em;font-weight:800;color:#147a74;margin-bottom:14px}
.qbody {font-size:clamp(17px,3vw,22px);color:#203a3c;line-height:2.05;font-weight:700;white-space:pre-wrap;overflow-wrap:anywhere}
.qname {font-size:31px;font-weight:800;color:#19484a;line-height:1.4;margin:2px 0 7px}
.card-topline {display:flex;justify-content:space-between;align-items:center; color:#506a6d;font-size:12px;font-weight:700}
.roundel {background:#ebf5f1;border:1px solid #cbdfd9;color:#196f65;border-radius:50px;padding:6px 12px;font-size:12px;font-weight:800}
.reveal {padding:20px 24px;border-radius:18px;background:#ebf5f2;border:1px solid #c7e1d8;margin:14px 0 18px}
.reveal .title {font-weight:800;color:#206a62;margin-bottom:6px}
.reveal .body {font-size:15px;line-height:1.9;overflow-wrap:anywhere}
.reveal a {color:#176e70;text-decoration:underline;text-underline-offset:3px;word-break:break-all}
.tiny {color:#627679;font-size:12px;line-height:1.7}
.footer {font-size:11px;color:#77918d;text-align:center;padding-top:30px;}
@media(max-width:640px){.hero{padding:25px 24px}.block-container{padding:1.1rem 1rem 3rem !important}.question{padding:17px 18px}}
</style>
''', unsafe_allow_html=True)


def safe(s):
    return html.escape(str(s), quote=True)


def display_hero():
    st.markdown('''<div class="hero"><div class="eyebrow">POKÉDEX · FIELD NOTES</div>
    <h1>そのポケモンの、<br>知らない一面。</h1>
    <p>名前の向こうにある、生態と物語を知ろう。<br>ゲーム内の図鑑原文だけで挑む、4択の知識クイズ。</p></div>''', unsafe_allow_html=True)


def source_block(quote):
    st.markdown(
        f'<div class="reveal"><div class="title">公式図鑑の原文</div>'
        f'<div class="body">{safe(quote["text"])}</div>'
        f'<div class="tiny" style="margin-top:10px">出典：{safe(quote["source_title"])}</div>'
        f'<div class="tiny"><a href="{safe(quote["url"])}" target="_blank" rel="noopener">公式図鑑で確かめる ↗</a></div></div>',
        unsafe_allow_html=True,
    )


def art_url(row):
    # HTML内の公式画像URLを優先。未取得の先行体験データには公開アートワークを利用。
    return row.get('image_url') or (
        f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{row['id']}.png"
    )


def start_game(db, region, mode, count, preview=False, chosen=None, review=False):
    region_ids = TARGET_IDS if region == '両地方' else REGIONS[region]
    chosen = chosen if chosen is not None else list(region_ids)
    questions = make_session(db, region, mode, count, preview=preview, target_ids=chosen)
    st.session_state.quiz = {'questions': questions, 'i': 0, 'answer': None,
                             'score': 0, 'missed': st.session_state.quiz['missed'] if review else [],
                             'region': region, 'mode': mode, 'preview': preview, 'review': review}
    st.rerun()


def show_landing(db):
    display_hero()
    st.markdown('<div class="section-title">冒険の準備</div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        region = st.selectbox('出題する地方', ['イッシュ','パルデア','両地方'], index=0)
    with right:
        count = st.selectbox('問題数', [10,20,30,50,'全問'], index=0)
    st.markdown('<div class="section-title">クイズのスタイル</div>', unsafe_allow_html=True)
    mode_label = st.radio('形式', ['図鑑の文章から当てる','ポケモンの名前から選ぶ','おまかせミックス'], index=0,
                          help='本文を伏せたり改変したりしません。文章に名前が含まれるときは逆向きに自動調整します。')
    mode = {'図鑑の文章から当てる':'who','ポケモンの名前から選ぶ':'which','おまかせミックス':'mix'}[mode_label]
    cov = coverage(db, region)
    st.markdown('<div class="section-title">公式図鑑の収録状況</div>', unsafe_allow_html=True)
    a,b,c = st.columns(3)
    a.metric('対象', f'{cov["target"]} 匹')
    b.metric('図鑑原文を登録', f'{len(cov["present"])} 匹')
    c.metric('公式HTMLから自動取得', f'{len(cov["fetched"])} 匹')
    st.progress(len(cov['present']) / cov['target'])
    if cov['missing']:
        st.info('現在のデータは収集中です。全種モードでは1匹も省略しません。データが揃うまで、下の体験モードで収録済みの問題を試せます。')
        with st.expander(f'未収録 {len(cov["missing"])}匹の番号を見る'):
            st.write('、'.join(f'{i:04d}' for i in cov['missing']))
        can_sample = len(cov['present']) >= 4
        if st.button('収録済みで体験する →', type='primary', disabled=not can_sample, use_container_width=True):
            start_game(db,region,mode,count,preview=True,chosen=cov['present'])
        st.caption('この体験モードは276匹完成版ではありません。図鑑原文が未収録の番号を自動的に埋めたり、公式以外の文章で代用したりしません。')
    else:
        if st.button('クイズをはじめる →', type='primary', use_container_width=True):
            start_game(db,region,mode,count)
    st.markdown('<div class="note">答え合わせでは作品名と公式出典へのリンクを表示。公式HPやポケカの情報は図鑑とは区別し、補足としてのみ紹介します。</div>', unsafe_allow_html=True)


def show_question(db, supplements):
    game=st.session_state.quiz
    idx=game['i']; questions=game['questions']
    if idx >= len(questions):
        show_end(db)
        return
    q=questions[idx]; pid=q['pokemon_id']; row=db['pokemon'][str(pid)]
    st.markdown('<div class="card-topline"><span>POKÉDEX QUIZ</span><span class="roundel">{} / {}</span></div>'.format(idx+1,len(questions)),unsafe_allow_html=True)
    st.progress(idx / len(questions))
    c1,c2=st.columns([3,1])
    c1.markdown(f'**{game["region"]}**  ・  {"図鑑 → ポケモン" if q["mode"] == "who" else "ポケモン → 図鑑"}')
    c2.markdown(f'<div class="tiny" style="text-align:right">正解 {game["score"]} 問</div>',unsafe_allow_html=True)

    if q['mode']=='who':
        st.markdown('<div class="question"><div class="qcaption">QUESTION · 生態を手掛かりに</div><div class="qbody">{}</div></div>'.format(safe(q['quote']['text'])),unsafe_allow_html=True)
        st.markdown('**この説明に当てはまるのは、どのポケモン？**')
    else:
        top_left,top_right=st.columns([2,1])
        with top_left:
            st.markdown('<div class="question"><div class="qcaption">QUESTION · 図鑑の文章を探そう</div><div class="qname">{}</div><div class="tiny">全国図鑑 No.{:04d}</div></div>'.format(safe(q['name']),pid),unsafe_allow_html=True)
        with top_right:
            st.image(art_url(row),width=185)
        st.markdown('**このポケモンの公式図鑑に書かれているのは、どの文章？**')

    if q['mode']=='who':
        rows=[st.columns(2),st.columns(2)]
        for choice_index,opt in enumerate(q['choices']):
            with rows[choice_index//2][choice_index%2]:
                label = f'{"ABCD"[choice_index]}   {db["pokemon"][str(opt["id"])]["name"]}'
                if st.button(label,key=f'choice_{idx}_{choice_index}',use_container_width=True,disabled=game['answer'] is not None):
                    game['answer']=choice_index
                    if choice_index == q['correct_index']:
                        game['score']+=1
                        if pid in game['missed'] and game['review']:
                            game['missed'].remove(pid)
                    elif pid not in game['missed']:
                        game['missed'].append(pid)
                    st.rerun()
    else:
        for choice_index,opt in enumerate(q['choices']):
            label=f'{"ABCD"[choice_index]}   {opt["text"]}'
            if st.button(label,key=f'choice_{idx}_{choice_index}',use_container_width=True,disabled=game['answer'] is not None):
                game['answer']=choice_index
                if choice_index==q['correct_index']:
                    game['score']+=1
                    if pid in game['missed'] and game['review']:
                        game['missed'].remove(pid)
                elif pid not in game['missed']:
                    game['missed'].append(pid)
                st.rerun()

    if game['answer'] is not None:
        correct=game['answer']==q['correct_index']
        (st.success if correct else st.error)(('正解！ ' if correct else '不正解。正解は ') + q['name'])
        if q['mode']=='who':
            reveal_left,reveal_right=st.columns([1,3])
            with reveal_left:
                st.image(art_url(row),width=180)
            with reveal_right:
                st.markdown(f'### No.{pid:04d} {q["name"]}')
                st.caption('ポケモンの見た目と図鑑の記述を一緒に覚えよう。')
        source_block(q['quote'])
        with st.expander('ほかの選択肢の公式出典を見る'):
            for j,opt in enumerate(q['choices']):
                if j==q['correct_index']:
                    continue
                st.markdown(f'**{db["pokemon"][str(opt["id"])]["name"]}** · {opt["quote"]["source_title"]}')
                st.caption(opt['quote']['text'])
                st.link_button('出典を開く ↗',opt['quote']['url'])
        extras=[s for s in supplements.get(str(pid),[]) if eligible_supplement(s)]
        if extras:
            with st.expander('もっと知る · 公式サイト / ポケカの補足'):
                for n,s in enumerate(extras):
                    st.markdown(f'**{s["kind"]}** · {s["source_title"]}')
                    st.write(s['text'])
                    if s['kind'] in {'ポケカ公式','公式大会'}:
                        st.caption('※大会環境やカード評価は当時の情報。直近3年の情報だけを表示。')
                    st.link_button('公式の原文を見る ↗',s['url'])
        if st.button('次の問題へ →' if idx+1<len(questions) else '結果を見る →',type='primary',use_container_width=True):
            game['i']+=1
            game['answer']=None
            st.rerun()
    else:
        st.markdown('<div class="note">回答後に公式原文の出典が表示されます。</div>',unsafe_allow_html=True)
    if st.button('終了して結果を見る',key=f'quit_{idx}'):
        game['i']=len(questions)
        st.rerun()


def show_end(db):
    game=st.session_state.quiz
    display_hero()
    total=len(game['questions'])
    st.markdown('### おつかれさまでした！')
    a,b,c=st.columns(3)
    a.metric('正解',f'{game["score"]} / {total}')
    b.metric('正答率',f'{game["score"]/total*100:.0f}%' if total else '–')
    c.metric('復習対象',f'{len(game["missed"])} 匹')
    if game['missed']:
        st.markdown('**もう一度覚えたいポケモン**')
        st.caption('、'.join(db['pokemon'][str(i)]['name'] for i in game['missed']))
        if st.button('間違えた問題を復習する →',type='primary',use_container_width=True):
            start_game(db,game['region'],game['mode'],'全問',preview=game['preview'],chosen=list(game['missed']),review=True)
    else:
        st.success('復習対象はありません。すべて正解です！')
    if st.button('コース選択に戻る',use_container_width=True):
        del st.session_state.quiz
        st.rerun()


try:
    DB=load_data()
    EXTRA=load_supplements()
except (OSError, ValueError, KeyError) as exc:
    st.error(f'固定問題ファイルが壊れているか未配置です。data/ フォルダを確認してください。詳細: {exc}')
    st.stop()

if 'quiz' not in st.session_state:
    show_landing(DB)
else:
    show_question(DB,EXTRA)
st.markdown('<div class="footer">非公式ファン制作 · ゲーム内図鑑の出典は各解説から確認できます</div>',unsafe_allow_html=True)
