"""画面構成の読み込みテスト。実際のブラウザー描画テストではない。"""
from pathlib import Path
import runpy
import sys
import types
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from quiz_core import load_data,coverage,make_session

class DummyContainer:
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def __getattr__(self,name):return lambda *args,**kwargs: None

class AttrDict(dict):
    def __getattr__(self,k):return self[k]
    def __setattr__(self,k,v):self[k]=v

class DummyStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__('streamlit')
        self.session_state=AttrDict()
        self.markdowns=[]
    def set_page_config(self,**kwargs):pass
    def markdown(self,value,**kwargs):self.markdowns.append(value)
    def columns(self,n):return [DummyContainer() for _ in range(n if isinstance(n,int) else len(n))]
    def selectbox(self,label,options,index=0,**kwargs):return options[index]
    def radio(self,label,options,index=0,**kwargs):return options[index]
    def button(self,*args,**kwargs):return False
    def metric(self,*args,**kwargs):pass
    def progress(self,*args,**kwargs):pass
    def info(self,*args,**kwargs):pass
    def caption(self,*args,**kwargs):pass
    def expander(self,*args,**kwargs):return DummyContainer()
    def image(self,*args,**kwargs):pass
    def success(self,*args,**kwargs):pass
    def error(self,*args,**kwargs):pass
    def write(self,*args,**kwargs):pass
    def link_button(self,*args,**kwargs):pass

class AppSmokeTests(unittest.TestCase):
    def run_app(self,state=None):
        old=sys.modules.get('streamlit')
        stub=DummyStreamlit()
        stub.session_state=AttrDict(state or {})
        sys.modules['streamlit']=stub
        try:runpy.run_path(str(ROOT/'app.py'),run_name='__main__')
        finally:
            if old is None:sys.modules.pop('streamlit',None)
            else:sys.modules['streamlit']=old
        return stub
    def test_landing(self):
        page=self.run_app()
        self.assertTrue(any('そのポケモンの' in v for v in page.markdowns))
    def test_in_quiz_before_and_after_answer(self):
        db=load_data()
        ids=coverage(db,'パルデア')['present']
        questions=make_session(db,'パルデア','who',4,target_ids=ids,seed=3)
        state={'quiz':{'questions':questions,'i':0,'answer':None,'score':0,'missed':[], 'region':'パルデア','mode':'who','preview':True,'review':False}}
        page=self.run_app(state)
        self.assertTrue(any('QUESTION' in v for v in page.markdowns))
        state['quiz']['answer']=questions[0]['correct_index']
        page=self.run_app(state)
        self.assertTrue(any('公式図鑑の原文' in v for v in page.markdowns))
    def test_finished_screen(self):
        state={'quiz':{'questions':[{'pokemon_id':494}],'i':1,'answer':None,'score':1,'missed':[], 'region':'イッシュ','mode':'who','preview':True,'review':False}}
        page=self.run_app(state)
        self.assertTrue(any('そのポケモンの' in v for v in page.markdowns))

if __name__=='__main__':unittest.main()
