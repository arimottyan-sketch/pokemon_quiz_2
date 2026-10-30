import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quiz_engine import read_db,eligible_extra,is_recent,validate_db,plan_extra_session
from progressive_quiz import progressive_pair,plan_progressive_session
from datetime import date

class TestTimelessCardSpeciesFlavor(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.db=read_db()
 def test_5_fresh_old_card_sources_are_playable_and_selected(self):
  for pid in (515,529,543,582,602):
   with self.subTest(pid=pid):
    rec=[q for q in self.db['pokemon'][str(pid)]['quotes'] if q.get('card_text_role')=='species_flavor'][-1]
    self.assertTrue(is_recent(rec,date(2026,10,30)))
    self.assertIn(rec,eligible_extra(self.db['pokemon'][str(pid)]))
    first,second=progressive_pair(self.db,pid)
    self.assertEqual(first['url'],rec['url'])
    self.assertNotEqual(first['text'],second['text'])
 def test_preexisting_flavor_is_no_longer_blocked(self):
  rec=[q for q in self.db['pokemon']['583']['quotes'] if q.get('card_text_role')=='species_flavor'][0]
  self.assertIn(rec,eligible_extra(self.db['pokemon']['583']))
 def test_old_card_mechanics_remain_age_limited(self):
  sample={'kind':'ポケカ公式','first_release_on':'2020-01-01'}
  self.assertFalse(is_recent(sample,date(2026,10,30)))
 def test_all_280_and_new_card_modes(self):
  self.assertEqual(len(plan_progressive_session(self.db,'両方','全問',seed=20261030)),280)
  for mode in ('extra_description','extra_picture','extra_mix'):
   questions=plan_extra_session(self.db,'両方',mode,'全問',priority_ids=[515,529,543,582,602],seed=20261030)
   self.assertTrue(questions)
   self.assertTrue(all(len(set(q['choices']))==4 for q in questions))
 def test_db_invariants(self):self.assertTrue(validate_db(self.db))
if __name__=='__main__':unittest.main()
