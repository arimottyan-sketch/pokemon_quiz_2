"""Final targeted test: dex then BW2 episode; permitted ability source is limited."""
import unittest, ast
from pathlib import Path
from quiz_engine import read_db, eligible_extra, question_passage, source_is_allowed
from progressive_quiz import progressive_pair, progressive_ids, plan_progressive_session, get_official_profile

class YanakkieFinalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=read_db()
    def test_yanakkie_hints_in_user_order(self):
        first,second=progressive_pair(self.db,512)
        self.assertEqual(first['kind'],'ゲーム内図鑑')
        self.assertEqual(second['kind'],'ゲーム公式HP')
        self.assertIn('気性が',first['text'])
        self.assertIn('元ジムリーダー',second['text'])
        self.assertIn('レストラン',question_passage(second,512,self.db))
        self.assertIn('2年後',question_passage(second,512,self.db))
        self.assertNotIn('ヤナッキー',question_passage(second,512,self.db))
        self.assertTrue(source_is_allowed(second))
        self.assertIn(second,eligible_extra(self.db['pokemon']['512']))
    def test_no_more_staged_fallback(self):
        for pid in progressive_ids(self.db,'両方'):
            first,second=progressive_pair(self.db,pid)
            self.assertFalse(first.get('progressive_staged',False),pid)
            self.assertFalse(second.get('progressive_staged',False),pid)
    def test_permitted_secondary_source_only_for_ability(self):
        profile=get_official_profile(self.db['pokemon']['512'], lambda url: self.fail('should work offline'))
        self.assertEqual(profile['types'],['くさ'])
        self.assertEqual(profile['abilities'],['くいしんぼう','しんりょく'])
        self.assertEqual(profile['hidden_abilities'],['しんりょく'])
        self.assertTrue(profile['hidden_abilities_verified'])
        self.assertEqual(profile['hidden_source_urls'], profile['permitted_nonofficial_ability_urls'])
        self.assertTrue(profile['hidden_source_urls'][0].startswith('https://yakkun.com/'))
    def test_required_app_profile_functions_exist(self):
        module=ast.parse((Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8'))
        definitions={node.name for node in module.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
        for name in ('cached_webpage','cached_official_profile','cached_zukan_profile'):
            self.assertIn(name,definitions)
    def test_all_280_remain_playable(self):
        session=plan_progressive_session(self.db,'両方','全問',seed=20261030)
        self.assertEqual(len(session),280)
        self.assertEqual(len({str(s['id']) for s in session}),280)
        self.assertTrue(all(len(set(s['choices']))==4 for s in session))

if __name__=='__main__': unittest.main()
