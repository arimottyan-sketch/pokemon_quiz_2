import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quiz_engine import read_db, eligible_extra, source_is_allowed, plan_extra_session, is_recent
from progressive_quiz import progressive_pair,plan_progressive_session
class SpeciesFirstQuality(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.db=read_db()
 def test_generic_moves_never_eligible(self):
  forbidden={504:'おさきにどうぞ',511:'アクロバット',513:'はじけるほのお',515:'ねっとう',978:'いっちょうあがり',602:'コミュニティ・デイ',1021:'じんらい'}
  for pid,term in forbidden.items():
   with self.subTest(pid=pid):
    for rec in eligible_extra(self.db['pokemon'][str(pid)]):
     self.assertNotIn(term,rec.get('question_text') or rec['text'])
 def test_replacements_are_official_and_not_generic_moves(self):
  for pid in [511,513,978]:
   one,two=progressive_pair(self.db,pid)
   self.assertTrue(source_is_allowed(one));self.assertTrue(source_is_allowed(two))
   self.assertFalse(one.get('progressive_staged'))
   self.assertNotIn('pokemongo.com',one['url'])
  self.assertIn('３００度',progressive_pair(self.db,513)[0]['text'])
  self.assertIn('指令',progressive_pair(self.db,978)[0]['text'])
 def test_504_resolved_with_distinct_official_card(self):
  a,b=progressive_pair(self.db,504)
  self.assertFalse(a.get('progressive_staged',False))
  self.assertNotEqual(a['text'],b['text'])
  self.assertIn('後ろからの 敵',a['text'])
 def test_280_playable_after_quality_upgrade(self):
  for seed in [13,28,501,20261028]:
   out=plan_progressive_session(self.db,'両方','全問',seed=seed)
   self.assertEqual(len(out),280)
   self.assertTrue(all(len(set(q['choices']))==4 for q in out))
 def test_unverified_signature_claim_not_used(self):
  row=self.db['pokemon']['1021']
  self.assertFalse(any('じんらい' in (r.get('question_text') or r['text']) for r in eligible_extra(row)))
  a,b=progressive_pair(self.db,1021)
  self.assertTrue(all(r['kind'].startswith('ゲーム内図鑑') for r in (a,b)))
  self.assertTrue(any('祖先' in r['text'] for r in (a,b)))
 def test_new_cards_respect_three_year_limit(self):
  for pid in (513,515,602):
   cards=[r for r in self.db['pokemon'][str(pid)]['quotes'] if r.get('first_release_on')=='2025-06-06']
   self.assertTrue(cards)
   self.assertTrue(all(is_recent(r) for r in cards))
if __name__=='__main__':unittest.main()
