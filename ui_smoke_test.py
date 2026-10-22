"""Mock Streamlit render-path check (not a real Streamlit browser test)."""
import sys,types,runpy
from pathlib import Path
ROOT=Path(__file__).parent
class State(dict):
    def __getattr__(self,k):return self[k]
    def __setattr__(self,k,v):self[k]=v
class Context:
    def __enter__(self):return self
    def __exit__(self,*a):return False
class Rerun(Exception):pass

class UI(types.ModuleType):
    def __init__(self,page='クイズ',finish_now=False):
        super().__init__('streamlit');self.page=page;self.finish_now=finish_now
        self.session_state=State();self.buttons=[];self.texts=[]
        self.cache_data=lambda *a,**kw:lambda func:func
    def __getattr__(self,name):
        if name in ('form','expander','container'):
            return lambda *args,**kwargs:Context()
        if name=='columns':
            return lambda n,**kwargs:[Context() for _ in range(n if isinstance(n,int) else len(n))]
        if name=='radio':
            return lambda label,*args,**kwargs: self.page if label=='画面' else None
        if name=='button':
            def hit(label,*args,**kwargs):
                self.buttons.append(label)
                return bool(self.finish_now and label=='ここまでで終了')
            return hit
        if name=='rerun':
            return lambda:Rerun()
        if name=='selectbox':
            return lambda label,options,**kwargs: options[0]
        if name=='text_input':
            return lambda *a,**k:''
        if name=='checkbox':return lambda *a,**k:False
        if name=='form_submit_button':return lambda *a,**k:False
        if name=='download_button':return lambda *a,**k:False
        if name in ('markdown','write','caption','error','success','warning','header','subheader','title','image','progress','metric','divider','set_page_config','info'):
            return lambda *a,**kw:self.texts.append((name,a))
        raise AttributeError(name)

# Generate a real question without rendering the first time.
ui0=UI('使い方');sys.modules['streamlit']=ui0
mod=runpy.run_path(str(ROOT/'app.py'))
db=mod['db']
for mode in ('picture','description','identification','extra_description','extra_picture'):
    q=mod['make_questions'](db,'パルデア',mode,ids=[906],seed=5)[0]
    ui=UI('クイズ')
    ui.session_state.update({'specs':[q],'idx':0,'score':1,'answer':True,
                             'missed':[],'bookmarked':[],'history':[],
                             'is_review':False,'region':'パルデア',
                             'quiz_style':mode,'finished':False})
    sys.modules['streamlit']=ui
    runpy.run_path(str(ROOT/'app.py'))
    assert '次の問題へ →' in ui.buttons and 'ここまでで終了' in ui.buttons,mode
    print('PASS rendered',mode)
# The early-finish button must work after the answer, without skipping the score.
q=mod['make_questions'](db,'パルデア','extra_picture',ids=[906],seed=8)[0]
ui=UI('クイズ',finish_now=True)
ui.session_state.update({'specs':[q],'idx':0,'score':1,'answer':True,
                         'missed':[],'bookmarked':[],'history':[],
                         'is_review':False,'region':'パルデア',
                         'quiz_style':'extra_picture','finished':False})
sys.modules['streamlit']=ui
try:runpy.run_path(str(ROOT/'app.py'))
except Rerun:pass
assert ui.session_state.finished is True and ui.session_state.score==1
print('PASS after-answer early finish, score preserved')
for page in ('ポケモン情報','使い方'):
    ui=UI(page);sys.modules['streamlit']=ui
    runpy.run_path(str(ROOT/'app.py'))
    print('PASS page',page)
print('PASS mock Streamlit render paths')
