"""Dependency-free checks; can run before deploying. Does not replace browser smoke test."""
import sys, types, runpy, json, time
from pathlib import Path

class Session(dict):
    def __getattr__(self, key):return self[key]
    def __setattr__(self,key,value):self[key]=value

st=types.ModuleType('streamlit')
st.session_state=Session()
for key in ['set_page_config','markdown','caption','title','subheader','warning']:
    setattr(st,key,lambda *a,**k:None)
st.cache_data=lambda *a,**k:lambda fn:fn
st.radio=lambda *a,**k:'使い方'
sys.modules['streamlit']=st
sys.modules['quiz_engine']=types.ModuleType('quiz_engine')
module=runpy.run_path(str(Path(__file__).with_name('app.py')))
db=module['db']
assert len(db['pokemon'])==280
assert sum(len(v['quotes']) for v in db['pokemon'].values())==467
assert all(module['source_is_allowed'](q) for row in db['pokemon'].values() for q in row['quotes'])
assert module['validate_db'](db)
labels=module['MODE_LABELS']
assert 'extra_picture' in labels and 'extra_description' in labels
for region in ('イッシュ','パルデア'):
    for mode in ('picture','description','identification','extra_description','extra_picture'):
        t0=time.monotonic()
        questions=module['make_questions'](db,region,mode,seed=42)
        assert questions, (region,mode)
        for q in questions:
            assert len(q['choices'])==4 and len(set(map(str,q['choices'])))==4
            assert q['id'] in q['choices']
            assert q['quotes'][q['id']]['text'] in [r['text'] for r in db['pokemon'][str(q['id'])]['quotes']]
            if mode in ('picture','extra_picture'):
                texts=[q['quotes'][x]['text'] for x in q['choices']]
                assert len(set(texts))==4
                if mode=='extra_picture':
                    assert all(q['quotes'][x]['kind'] != 'ゲーム内図鑑' for x in q['choices'])
        print('PASS',region,mode,len(questions),f'{time.monotonic()-t0:.1f}s')
    mixed=module['plan_session'](db,region,'mix',20,seed=7)
    assert len(mixed)==20
    single=module['plan_session'](db,region,'extra_picture',1,seed=9)
    assert len(single)==1
# Named species should be hidden ONLY for that choice; embedded unrelated species intact.
assert module['display_quote']('パモとパモットは仲間。', 921, db)=='？？？とパモットは仲間。'
assert module['display_quote']('パモとパモットは仲間。', 922, db)=='パモと？？？は仲間。'
# Short subjective example should choose reasonably similar distractors.
q=next(x for x in module['make_questions'](db,'パルデア','extra_description',seed=31) if x['id']==906)
assert len(q['choices'])==4
# Test the explicit "after answering" finish-button UI by looking for both active controls.
import inspect
app_txt=Path(__file__).with_name('app.py').read_text(encoding='utf-8')
assert "finish_clicked = st.button('ここまでで終了'" in app_txt
assert 'if finish_clicked:' in app_txt
assert "'extra_picture': '名前・姿 → 公式情報'" in app_txt
assert "elif kind in ('picture', 'extra_picture')" in app_txt
# All new official excerpts are byte-identical to substrings of source sentences saved in the audit.
import csv
with Path(__file__).with_name('NEW_VERIFIED_OFFICIAL_QUOTES.csv').open(encoding='utf-8-sig',newline='') as f:
    audit=list(csv.DictReader(f))
assert len(audit)==9
for row in audit:
    assert row['verbatim_excerpt'] in row['official_sentence_confirmed']
    assert any(x['text']==row['verbatim_excerpt'] and x['url']==row['url']
               for x in db['pokemon'][row['id']]['quotes'])
print('PASS 280 species/forms, 467 unchanged-or-official records, modes, source audit, original quote masking, finish UI')
