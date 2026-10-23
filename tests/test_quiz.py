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
        self.assertGreaterEqual(q.extra_record_count(DB,'両方'),100)
        self.assertEqual(len(AUD),226)
        self.assertEqual(q.extra_record_count(DB,'両方'),127)
        self.assertGreaterEqual(len(q.pool_ids(DB,'両方','extra_description')),80)
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
                            seen=[q.question_passage(task['quotes'][p],p,DB) for p in task['choices']]
                            self.assertEqual(len(set(seen)),4)
                        if task['mode'] in ('description','extra_description'):
                            shown=q.question_passage(task['quotes'][task['id']],task['id'],DB)
                            self.assertNotIn(DB['pokemon'][str(task['id'])]['name'],shown)
    def test_mixed_and_single_review(self):
        for region in ['イッシュ','パルデア','両方']:
            for count in [5,10,30]:
                qs=q.plan_session(DB,region,'mix',count,seed=38)
                self.assertEqual(len(qs),count)
                self.assertEqual(len({str(x['id']) for x in qs}),count)
        one=q.plan_session(DB,'パルデア','extra_mix','全問',priority_ids=[1012],seed=15)
        self.assertGreaterEqual(len(one),1)
    def test_excluded_cannot_reenter_quiz(self):
        for a in AUD:
            row=DB['pokemon'][str(a['id'])]
            rec=row['quotes'][int(a['quote_index'])]
            if rec.get('quality_repair') not in ('repaired_from_official_context', 'excluded_ambiguous_or_fragment','excluded_unresolved_fragment','excluded_semantically_ambiguous'):
                self.assertEqual(rec['quiz_approved'],a['quiz_approved']=='True')
            if not rec.get('quiz_approved'):
                self.assertNotIn(rec, q.eligible_extra(row))

class TestQualityRepair(unittest.TestCase):
    def test_originals_preserved_and_context_improved(self):
        examples=[('924',1,'第38話'),('566',2,'アララギ博士'),('1021',2,'首の先にある体毛'),
                  ('1009',2,'額には特徴的'),('1010',2,'金属のような質感'),('911',1,'歌声')]
        for pid,idx,word in examples:
            rec=DB['pokemon'][pid]['quotes'][idx]
            self.assertIn(word,rec['question_text'])
            self.assertEqual(rec['text'],SOURCE['pokemon'][pid]['quotes'][idx]['text'])
        for pid,idx in [('968',2),('907',3)]:
            self.assertNotIn(DB['pokemon'][pid]['quotes'][idx],q.eligible_extra(DB['pokemon'][pid]))
    def test_recovered_contextual_options(self):
        for pid,idx in [('501',5),('908',5),('910',3),('939',1),('1025',3)]:
            r=DB['pokemon'][pid]['quotes'][idx]
            self.assertTrue(r['quiz_approved'])
            self.assertIn('question_text',r)
            self.assertEqual(r['text'],SOURCE['pokemon'][pid]['quotes'][idx]['text'])

    def test_ui_feedback_and_title(self):
        source=(ROOT/'app.py').read_text(encoding='utf8')
        self.assertIn("st.title('ポケモンクイズ')",source)
        self.assertIn('正しい選択肢：',source)
        self.assertNotIn('正解は {row',source)
        self.assertNotIn('適用範囲：',source)
    def test_question_passage_keeps_source_and_masks_correct_name_only(self):
        pid='924';rec=DB['pokemon'][pid]['quotes'][1]
        shown=q.question_passage(rec,924,DB)
        self.assertIn('第38話',shown)
        self.assertIn('？？？',shown)
        self.assertNotIn('ワッカネズミ',shown)
        self.assertEqual(rec['text'],SOURCE['pokemon'][pid]['quotes'][1]['text'])

if __name__=='__main__':unittest.main()
