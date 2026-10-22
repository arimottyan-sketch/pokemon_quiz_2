"""Offline import-time smoke test with Streamlit's public UI calls stubbed.
This is NOT a real Streamlit browser or deploy test.
"""
import contextlib
import importlib.util
import pathlib
import sys
import types
import unittest

BASE=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from quiz_engine import read_db
from staff_learning import plan_session

class State(dict):
    def __getattr__(self,k):
        try:return self[k]
        except KeyError:raise AttributeError(k)
    def __setattr__(self,k,v):self[k]=v

class UI:
    def __init__(self,page='クイズで覚える',state=None):
        self.page=page
        self.session_state=state or State()
        self.calls=[]
        self.cache_data=lambda **kw: (lambda f:f)
    def __getattr__(self,name):
        if name in ('columns',):return lambda n,**kw:[self for _ in range(n)]
        if name in ('radio',):
            def func(label,options,**kw):
                self.calls.append((name,label))
                return self.page if label=='画面' else (kw.get('index',0) if label=='選択肢' else options[0])
            return func
        if name=='selectbox':return lambda label,opts,**kw:opts[kw.get('index',0)]
        if name=='text_input':return lambda *a,**kw:''
        if name=='checkbox':return lambda *a,**kw:False
        if name in ('button','form_submit_button'):return lambda *a,**kw:False
        if name=='form':return lambda *a,**kw:self
        if name=='expander':return lambda *a,**kw:self
        if name=='progress':return lambda *a,**kw:None
        if name=='stop':return lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('st.stop'))
        return lambda *a,**kw:None
    def __enter__(self):return self
    def __exit__(self,*exc):return False

class Smoke(unittest.TestCase):
    def render(self,page,state=None):
        fake=UI(page,state)
        st=types.ModuleType('streamlit')
        st.__getattr__=fake.__getattr__
        st.session_state=fake.session_state
        st.cache_data=fake.cache_data
        old=sys.modules.get('streamlit')
        sys.modules['streamlit']=st
        try:
            name='app_smoke_unique'
            spec=importlib.util.spec_from_file_location(name,BASE/'app.py')
            m=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
        finally:
            if old is None:sys.modules.pop('streamlit',None)
            else:sys.modules['streamlit']=old
        return fake
    def test_start_page(self):self.render('クイズで覚える')
    def test_lookup_page(self):self.render('ポケモンを調べる')
    def test_help_page(self):self.render('学習の使い方')
    def test_question_and_reveal(self):
        q=plan_session(read_db(),'パルデア','mix',5,seed=4)
        for stage in (None,True):
            state=State(specs=q,idx=0,score=0,answer=stage,missed=[],bookmarked=[],
                        history=[],is_review=False,region='パルデア',quiz_style='mix',finished=False)
            self.render('クイズで覚える',state)
    def test_finish(self):
        q=plan_session(read_db(),'イッシュ','mix',3,seed=4)
        self.render('クイズで覚える',State(specs=q,idx=3,score=2,answer=None,missed=[],
                    bookmarked=[],history=[],is_review=False,region='イッシュ',quiz_style='mix',finished=True))
if __name__=='__main__':unittest.main()
