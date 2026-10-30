"""Additional card-flavor provenance, independent clues, and quiz-mode regressions."""
import csv,unittest
from pathlib import Path
from datetime import date
from quiz_engine import read_db,eligible_extra,source_is_allowed,is_recent,plan_extra_session,question_passage
from progressive_quiz import progressive_pair,plan_progressive_session
ROOT=Path(__file__).resolve().parents[1]

class Enrichment(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.db=read_db()
  with (ROOT/'data/POKEMON_CARD_FLAVOR_ENRICHMENT_20261030.csv').open(encoding='utf-8-sig',newline='') as f:
   cls.rows=list(csv.DictReader(f))
 def test_new_records_exactly_12_plus_one_reenabled(self):
  self.assertEqual(len(self.rows),13)
  self.assertEqual(sum(x['action']=='追加' for x in self.rows),12)
  self.assertEqual(sum(len(q['quotes']) for q in self.db['pokemon'].values()),829)
  for entry in self.rows:
   pid=entry['id']; recs=[q for q in self.db['pokemon'][pid]['quotes'] if q['url']==entry['official_url']]
   self.assertEqual(len(recs),1,pid)
   q=recs[0]
   self.assertTrue(source_is_allowed(q),pid)
   self.assertEqual(q['text'],entry['official_text'])
   self.assertEqual(q.get('question_text',q['text']),entry['quiz_display_text'])
   self.assertTrue(q['quiz_approved'])
   self.assertTrue(q['quiz_enabled'])
   self.assertEqual(q['card_text_role'],'species_flavor')
   self.assertTrue(is_recent(q,date(2026,10,30)))
   self.assertIn(q,eligible_extra(self.db['pokemon'][pid]))
   a,b=progressive_pair(self.db,int(pid))
   self.assertEqual(a['url'],q['url'])
   self.assertNotEqual(a['text'],b['text'])
 def test_280_distinct_including_yanakkie(self):
  ids=[504,519,522,527,528,540,567,577,600,610,611,625,997]
  for pid in ids:
   a,b=progressive_pair(self.db,pid)
   self.assertFalse(a.get('progressive_staged',False),pid)
  staged=[p for p in [*range(494,650),*range(906,1026), '128-paldea-combat', '128-paldea-blaze','128-paldea-aqua','194-paldea']
          if str(p) in self.db['pokemon'] and progressive_pair(self.db,p)[0].get('progressive_staged')]
  self.assertEqual(staged,[])
  a,b=progressive_pair(self.db,512)
  self.assertNotEqual(a['text'],b['text'])
  self.assertEqual(a['kind'],'ゲーム内図鑑')
  self.assertEqual(b['kind'],'ゲーム公式HP')
 def test_quiz_execution_4_choices_and_standalone(self):
  for seed in (42,20261030,321):
   session=plan_progressive_session(self.db,'両方','全問',seed=seed)
   self.assertEqual(len(session),280)
   self.assertEqual(len({str(q['answer']) for q in session}),280)
   self.assertTrue(all(len(q['choices'])==4 and len(set(q['choices']))==4 and q['answer'] in q['choices'] for q in session))
  for mode in ('extra_description','extra_picture','extra_mix'):
   session=plan_extra_session(self.db,'両方',mode,'全問',priority_ids=[int(x['id']) for x in self.rows],seed=321)
   self.assertTrue(session)
   self.assertTrue(all(len(set(q['choices']))==4 for q in session))
 def test_no_unintended_url_or_question_leak(self):
  for entry in self.rows:
   pid=int(entry['id']); q=progressive_pair(self.db,pid)[0]
   self.assertEqual(question_passage(q,pid,self.db),entry['quiz_display_text'].replace(self.db['pokemon'][entry['id']]['name'],'？？？'))

if __name__=='__main__':unittest.main()
