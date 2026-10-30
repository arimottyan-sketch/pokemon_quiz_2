"""Regression checks for targeted official-source-only clue quality fixes."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quiz_engine import read_db, question_passage, source_is_allowed
from progressive_quiz import progressive_pair, plan_progressive_session

class QualityImprovements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = read_db()

    def test_new_selection_prioritizes_useful_verified_facts(self):
        for pid in (511,513,515,548,572,582,608,613,998):
            with self.subTest(pid=pid):
                first, second = progressive_pair(self.db,pid)
                self.assertTrue(source_is_allowed(first))
                self.assertTrue(source_is_allowed(second))
                self.assertNotIn('pokemongo.com',first.get('url',''))
                self.assertNotIn('poketoru',first.get('source_title','').lower())
                self.assertNotEqual(question_passage(first,pid,self.db),question_passage(second,pid,self.db))

    def test_mega_is_explicit_in_hint_and_not_basic_quiz(self):
        first,_=progressive_pair(self.db,998)
        self.assertIn('メガ',first['question_text'])
        self.assertTrue(first['require_special_form_image'])
        self.assertTrue(first['progressive_allow_mega_hint'])
        self.assertEqual(first['source_title'],'『Pokémon LEGENDS Z-A M次元ラッシュ』メガセグレイブ紹介')

    def test_all_280_produce_unique_four_choices(self):
        questions=plan_progressive_session(self.db,'両方','全問',seed=20261028)
        self.assertEqual(len(questions),280)
        self.assertTrue(all(len(set(q['choices']))==4 for q in questions))

    def test_no_nonofficial_primary_quote_domains(self):
        for row in self.db['pokemon'].values():
            for quote in row['quotes']:
                self.assertTrue(source_is_allowed(quote),quote['url'])

if __name__ == '__main__':
    unittest.main()
