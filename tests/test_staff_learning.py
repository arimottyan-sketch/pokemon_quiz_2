"""Checks staff modes without requiring Streamlit or external connectivity."""
import csv
import hashlib
import io
import json
import pathlib
import sys
import unittest

BASE=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from quiz_engine import read_db,REGIONS,pokedex_records,national_number,display_quote
from staff_learning import (MODE_LABELS,pool_ids,eligible_extra,plan_session,
                            progress_csv,make_history,region_for)

class StaffLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=read_db()
        cls.source=(BASE/'data'/'official_quotes.json').read_bytes()
        cls.source_checksum=hashlib.sha256(cls.source).hexdigest()

    def test_unchanged_official_quotes(self):
        self.assertEqual(hashlib.sha256((BASE/'data'/'official_quotes.json').read_bytes()).hexdigest(),self.source_checksum)
        self.assertEqual(len(self.db['pokemon']),280)
        self.assertEqual(len(REGIONS['イッシュ']),156)
        self.assertEqual(len(REGIONS['パルデア']),124)

    def test_many_ways_of_learning(self):
        for region in ('イッシュ','パルデア','両方'):
            for mode in MODE_LABELS:
                q=plan_session(self.db,region,mode,10,seed=20261022)
                self.assertEqual(len(q),10,(region,mode))
                for one in q:
                    self.assertIn(one['id'],one['choices'])
                    self.assertEqual(len(one['choices']),4)
                    self.assertEqual(len(set(map(str,one['choices']))),4)
                    self.assertIn(one['id'],one['quotes'])
                    self.assertIn(one['mode'],MODE_LABELS)
                    if one['mode']=='extra_description':
                        self.assertIn(one['quotes'][one['id']],eligible_extra(self.db['pokemon'][str(one['id'])]))
                    if one['mode']=='picture':
                        self.assertEqual(len(one['quotes']),4)
                        self.assertEqual(len({x['text'] for x in one['quotes'].values()}),4)

    def test_review_and_regional(self):
        pid = REGIONS['パルデア'][0]
        q=plan_session(self.db,'両方','mix',20,priority_ids=[pid],seed=4)
        self.assertEqual(len(q),1)
        self.assertEqual(q[0]['id'],pid)
        self.assertEqual(region_for(pid),'パルデア')
        form='128-paldea-combat'
        q=plan_session(self.db,'パルデア','identification',1,priority_ids=[form])
        self.assertEqual(len(q),1)
        self.assertEqual(q[0]['id'],form)
        self.assertEqual(national_number(self.db['pokemon'][form]),128)

    def test_extra_only_includes_eligible(self):
        ids=pool_ids(self.db,'両方','extra_description')
        self.assertGreater(len(ids),20)
        for pid in ids:
            self.assertTrue(eligible_extra(self.db['pokemon'][str(pid)]))
        quotes=[q['quotes'][q['id']] for q in plan_session(self.db,'両方','extra_description','全問',seed=12)]
        self.assertTrue(all(q['kind'] not in ('ポケカ公式','大会公式') for q in quotes))

    def test_mask_changes_only_display_not_original(self):
        before=(BASE/'data'/'official_quotes.json').read_bytes()
        display_quote('パモとパモット','921',self.db)
        self.assertEqual((BASE/'data'/'official_quotes.json').read_bytes(),before)

    def test_history_csv_export(self):
        data=progress_csv([make_history(494,'identification',True)],self.db)
        r=list(csv.reader(io.StringIO(data.lstrip('\ufeff'))))
        self.assertEqual(len(r),2)
        self.assertEqual(r[1][3],'ビクティニ')
        self.assertEqual(r[1][-1],'正解')

    def test_app_ui_has_actions(self):
        txt=(BASE/'app.py').read_text(encoding='utf-8')
        for needle in ('st.form_submit_button','st.columns(2)','公式トリビア','この子を1問練習',
                       '学習履歴をCSVで保存','公式の掲載ページ','display_quote','PokeAPI','st.progress'):
            self.assertIn(needle,txt)
        self.assertNotIn('カード・大会情報は過去約3年',txt)

if __name__=='__main__': unittest.main()
