"""Runs startup without Streamlit installed, using only a fake UI interface."""
import sys, types, runpy, random
from pathlib import Path

class Session(dict):
    def __getattr__(self,key): return self[key]
    def __setattr__(self,key,value): self[key]=value

st = types.ModuleType('streamlit')
st.session_state=Session()
st.set_page_config=lambda **k: None
st.markdown=lambda *a,**k: None
st.caption=lambda *a,**k: None
st.title=lambda *a,**k: None
st.subheader=lambda *a,**k: None
st.warning=lambda *a,**k: None
st.cache_data=lambda *a,**k: (lambda fn: fn)
st.radio=lambda *a,**k: '使い方'
sys.modules['streamlit']=st
# Break any old modules deliberately: app.py must not import them.
sys.modules['quiz_engine']=types.ModuleType('quiz_engine')
sys.modules['legacy_learning']=types.ModuleType('legacy_learning')
module=runpy.run_path(str(Path(__file__).parent/'app.py'))
db=module['db']
assert len(db['pokemon']) == 280
assert sum(len(x['quotes']) for x in db['pokemon'].values()) == 458
for region in ('イッシュ','パルデア'):
    for mode in ('picture','description','identification'):
        results=module['make_questions'](db,region,mode,seed=99)
        assert results and all(len(q['choices'])==4 and q['id'] in q['choices'] for q in results)
    prompts=module['plan_session'](db,region,'mix',10,seed=3)
    assert len(prompts)==10
print('OK: independent app imports; 280 forms; 458 quotes; quiz generation checks')
