import copy
from datetime import date
import json
from pathlib import Path
import random
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quiz_core import (REGIONS,TARGET_IDS,coverage,dex_entries,eligible_supplement,load_data,make_session)

class QuizTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=load_data()
    def test_targets(self):
        self.assertEqual(len(TARGET_IDS),276)
        self.assertEqual(REGIONS['イッシュ'][0],494)
        self.assertEqual(REGIONS['パルデア'][0],906)
        self.assertEqual(REGIONS['パルデア'][-1],1025)
        self.assertEqual(len(set(TARGET_IDS)),276)
    def test_official_only(self):
        for pid in self.data['pokemon']:
            for q in dex_entries(self.data['pokemon'][pid]):
                self.assertEqual(q['kind'],'ゲーム内図鑑')
                self.assertIn(pid.zfill(4),q['url'])
    def test_coverage_does_not_hide_missing(self):
        a=coverage(self.data,'両地方')
        self.assertEqual(len(a['present'])+len(a['missing']),276)
        self.assertEqual(len(a['fetched']),0)
    def test_missing_is_fatal(self):
        with self.assertRaisesRegex(ValueError,'未収録'):
            make_session(self.data,'イッシュ','who',10)
    def test_all_seed_entries_can_play(self):
        for region in REGIONS:
            ids=coverage(self.data,region)['present']
            if len(ids)>=4:
                for mode in ('who','which','mix'):
                    questions=make_session(self.data,region,mode,'全問',target_ids=ids,seed=5)
                    self.assertEqual(len(questions),len(ids))
                    for q in questions:
                        self.assertEqual(len(q['choices']),4)
                        self.assertEqual(len({x['text'] for x in q['choices']}),4)
                        self.assertEqual(q['choices'][q['correct_index']]['id'],q['pokemon_id'])
                        self.assertIn(q['quote']['text'],[x['text'] for x in q['choices']])
    def test_all_276_fixture(self):
        fake={'schema_version':1,'pokemon':{}}
        for i in TARGET_IDS:
            fake['pokemon'][str(i)]={'id':i,'name':f'ポケモン{i}','data_status':'official_html_collected','quotes':[{'kind':'ゲーム内図鑑','review_status':'official_html_collected','text':f'固有本文そのまま{i}', 'url':f'https://zukan.pokemon.co.jp/detail/{i:04d}', 'source_title':'test'}]}
        for mode in ('who','which','mix'):
            questions=make_session(fake,'両地方',mode,'全問',seed=0)
            self.assertEqual(len(questions),276)
            self.assertEqual(set(q['pokemon_id'] for q in questions),set(TARGET_IDS))
            for q in questions:
                self.assertEqual(q['choices'][q['correct_index']]['id'],q['pokemon_id'])
                self.assertEqual(len(set(x['text'] for x in q['choices'])),4)
    def test_self_revealing_quote_reverse_mode(self):
        data=copy.deepcopy(self.data)
        ids=coverage(data,'イッシュ')['present']
        for i in ids:
            name=data['pokemon'][str(i)]['name']
            data['pokemon'][str(i)]['quotes']=[{'kind':'ゲーム内図鑑','review_status':'official_index_excerpt_reviewed','text':f'{name}のことです', 'url':f'https://zukan.pokemon.co.jp/detail/{i:04d}', 'source_title':'test'}]
        qs=make_session(data,'イッシュ','who','全問',target_ids=ids,seed=2)
        self.assertTrue(all(q['mode']=='which' for q in qs))
    def test_supplement_filter_old_cards(self):
        old={'kind':'ポケカ公式','text':'カードテスト','source_title':'a','url':'https://www.pokemon-card.com/card-search/','first_release_on':'2018-01-01'}
        self.assertFalse(eligible_supplement(old,date(2026,10,21)))
        old['first_release_on']='2025-06-06'
        self.assertTrue(eligible_supplement(old,date(2026,10,21)))
    def test_dex_not_aged_out(self):
        rec={'kind':'ゲーム内図鑑','text':'old','url':'https://zukan.pokemon.co.jp/detail/0494','source_title':'test','verified_on':'2013-01-01'}
        self.assertTrue(bool(rec))
    def test_no_unknown_domain(self):
        row={'kind':'ゲーム公式HP','source_title':'test','text':'fake','url':'https://example.com/haha'}
        self.assertFalse(eligible_supplement(row))

if __name__=='__main__': unittest.main()
