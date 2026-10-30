import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quiz_engine import read_db,eligible_extra,plan_session
from progressive_quiz import progressive_pair,plan_progressive_session
class EditorialQuality20261029(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.db=read_db()
 def test_weak_records_are_excluded_all_quiz_modes(self):
  ids=[504,510,511,512,515,529,543,548,582,591,602,997]
  for id in ids:
   for r in self.db['pokemon'][str(id)]['quotes']:
    if r.get('editorial_status')=='excluded_low_species_learning_value_20261029':
     self.assertNotIn(r,eligible_extra(self.db['pokemon'][str(id)]),id)
 def test_clear_no_more_staging_for_yanakkie(self):
  for pid in (512,):
   a,b=progressive_pair(self.db,pid)
   self.assertFalse(a.get('progressive_staged'),pid)
   self.assertNotEqual(a['text'],b['text'])
  for pid in (504,515,529,543,582,602,997):
   a,b=progressive_pair(self.db,pid)
   self.assertFalse(a.get('progressive_staged',False),pid)
   self.assertNotEqual(a['text'],b['text'])
 def test_yanapp_2025_card_ecology_not_incidental_anime(self):
  a,b=progressive_pair(self.db,511)
  self.assertIn('深い 森で 暮らす',a['text'])
  self.assertEqual(a['kind'],'ポケカ公式')
  self.assertEqual(a['first_release_on'],'2025-06-06')
  self.assertNotIn('ユキノオー',a['text'])
 def test_churine_uses_two_game_dex_entries(self):
  a,b=progressive_pair(self.db,548)
  self.assertTrue(all(x['kind'].startswith('ゲーム内図鑑') for x in [a,b]))
 def test_amongus_mushroom_card_is_meaningful_official_but_same_topic(self):
  a,b=progressive_pair(self.db,591)
  self.assertEqual(a['kind'],'ポケカ公式')
  self.assertIn('ダンス',a['text'])
  self.assertIn('だまされる',b['text'])
 def test_all_280_still_playable(self):
  for seed in (1,42,20261029):
   out=plan_progressive_session(self.db,'両方','全問',seed=seed)
   self.assertEqual(len(out),280)
   self.assertTrue(all(len(set(q['choices']))==4 for q in out))
if __name__=='__main__':unittest.main()
