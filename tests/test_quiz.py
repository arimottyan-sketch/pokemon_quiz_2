"""Regression tests: python -m unittest discover -s tests -v"""
import unittest, sys, json, random, hashlib, csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import quiz_engine as q
ROOT=Path(__file__).resolve().parents[1]
DB=q.read_db()
SOURCE=json.loads((ROOT/'data/source_original_631.json').read_text(encoding='utf-8'))
AUD=list(csv.DictReader((ROOT/'data/non_dex_full_audit.csv').open(encoding='utf-8-sig')))

class TestQuiz(unittest.TestCase):
    def test_scope_and_source_integrity(self):
        self.assertEqual(len(DB['pokemon']),280)
        self.assertEqual(len(q.REGIONS['イッシュ']),156)
        self.assertEqual(len(q.REGIONS['パルデア']),124)
        self.assertEqual(sum(len(p['quotes']) for p in DB['pokemon'].values()),631)
        for pid,row in SOURCE['pokemon'].items():
            self.assertIn(pid, DB['pokemon'])
            updated=DB['pokemon'][pid]['quotes']
            self.assertEqual(len(updated),len(row['quotes']))
            for x,y in zip(row['quotes'],updated):
                self.assertEqual(x['text'],y['text'])
                self.assertEqual(x['url'],y['url'])
                self.assertEqual(x['source_title'],y['source_title'])
                self.assertEqual(x['kind'],y['kind'])
        self.assertEqual(sum(len(q.pokedex_records(row)) for row in DB['pokemon'].values()),405)
    def test_manifest_and_regressions(self):
        self.assertEqual(len(AUD),226)
        self.assertEqual(sum(item['quiz_approved']=='True' for item in AUD),163)
        self.assertEqual(sum(item['quiz_approved']=='False' for item in AUD),63)
        self.assertEqual(q.extra_record_count(DB,'両方'),163)
        self.assertEqual(len(q.pool_ids(DB,'両方','extra_description')),110)
        self.assertFalse(q.eligible_extra(DB['pokemon']['987']))
        self.assertFalse(any(rec['quiz_approved'] for rec in DB['pokemon']['494']['quotes'] if rec['kind']=='ポケカ公式'))
        self.assertTrue(any(r['kind']=='公式小説' for r in q.eligible_extra(DB['pokemon']['931'])))
    def test_all_dedicated_extras_appear_separately(self):
        for region in ['イッシュ','パルデア','両方']:
            total=q.extra_record_count(DB,region)
            qs=q.plan_session(DB,region,'extra_mix','全問',seed=13)
            self.assertEqual(len(qs),total)
            self.assertEqual(len(set((str(p['id']),p['source_record_index']) for p in qs)),total)
            for task in qs:
                self.assertEqual(task['choices'].count(task['id']),1)
                self.assertEqual(len(set(map(str,task['choices']))),4)
                self.assertEqual(task['quotes'][task['id']]['quiz_approved'],True)
                self.assertIn(task['quotes'][task['id']]['text'], [r['text'] for r in SOURCE['pokemon'][str(task['id'])]['quotes']])
                if task['quotes'][task['id']].get('require_special_form_image'):
                    self.assertEqual(task['mode'],'extra_description')
                    self.assertTrue(task.get('force_text_choices'))
    def test_distractors_unique_and_masked(self):
        for region in ['イッシュ','パルデア']:
            for mode in ['extra_description','extra_picture','extra_mix','description','picture','identification']:
                for seed in [1,42]:
                    qs=q.plan_session(DB,region,mode,20,seed=seed)
                    self.assertEqual(len(qs),20)
                    for task in qs:
                        self.assertEqual(len(task['choices']),4)
                        self.assertEqual(len(set(map(str,task['choices']))),4)
                        if task['mode'] in ('picture','extra_picture'):
                            seen=[q.display_quote(task['quotes'][p]['text'],p,DB) for p in task['choices']]
                            self.assertEqual(len(set(seen)),4)
                        if task['mode'] in ('description','extra_description'):
                            shown=q.display_quote(task['quotes'][task['id']]['text'],task['id'],DB)
                            self.assertNotIn(DB['pokemon'][str(task['id'])]['name'],shown)
    def test_mixed_and_single_review(self):
        for region in ['イッシュ','パルデア','両方']:
            for count in [5,10,30]:
                qs=q.plan_session(DB,region,'mix',count,seed=38)
                self.assertEqual(len(qs),count)
                self.assertEqual(len({str(x['id']) for x in qs}),count)
        one=q.plan_session(DB,'パルデア','extra_mix','全問',priority_ids=[1012],seed=15)
        self.assertEqual(len(one),4)
    def test_excluded_cannot_reenter_quiz(self):
        for a in AUD:
            row=DB['pokemon'][str(a['id'])]
            rec=row['quotes'][int(a['quote_index'])]
            self.assertEqual(rec['quiz_approved'],a['quiz_approved']=='True')
            if a['quiz_approved']=='False':
                self.assertNotIn(rec, q.eligible_extra(row))

if __name__=='__main__':unittest.main()
