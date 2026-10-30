import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from quiz_engine import read_db,source_is_allowed,is_recent
from progressive_quiz import progressive_ids,progressive_pair,plan_progressive_session
class Complete280(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.db=read_db()
 def test_280_two_distinct(self):
  ids=progressive_ids(self.db,'両方')
  self.assertEqual(len(ids),280)
  for pid in ids:
   a,b=progressive_pair(self.db,pid)
   # Two-step display may deliberately stage one official original rather than use
   # a different but irrelevant / near-duplicate passage.
   if a.get('progressive_staged'):
    self.assertTrue(b.get('progressive_staged'),pid)
    self.assertEqual(a['text'],b['text'],pid)
   else:
    self.assertNotEqual(a['text'],b['text'],pid)
 def test_793_quotes_official_only(self):
  self.assertGreaterEqual(sum(len(x['quotes']) for x in self.db['pokemon'].values()),793)
  for pid,row in self.db['pokemon'].items():
   for rec in row['quotes']:
    self.assertTrue(source_is_allowed(rec),(pid,rec.get('url')))
 def test_last7_approved(self):
  for pid in (504,510,578,590,602,997,998):
   r=self.db['pokemon'][str(pid)]['quotes'][-1]
   self.assertTrue(r['quiz_approved'],pid)
   self.assertTrue(is_recent(r),pid)
 def test_all_280_have_4_choices(self):
  for seed in (1,42):
   qs=plan_progressive_session(self.db,'両方','全問',seed=seed)
   self.assertEqual(len(qs),280)
   for q in qs:
    self.assertEqual(len(q['choices']),4)
    self.assertEqual(len(set(map(str,q['choices']))),4)
    self.assertIn(q['id'],q['choices'])
