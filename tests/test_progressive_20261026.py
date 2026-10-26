"""Progressive mode: fixed-source, scoring, parsing and species restrictions."""
import unittest
from pathlib import Path
from progressive_quiz import (
    PROGRESSIVE_MODE, MAX_HINTS, progressive_ids, progressive_pair,
    plan_progressive_session, parse_official_zukan_html, get_official_profile,
    hint_points, official_zukan_url)
from quiz_engine import read_db, REGIONS, question_passage


class ProgressiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = read_db()

    def test_only_distinct_official_clues_and_approved_extra(self):
        ids = progressive_ids(self.db, '両方')
        self.assertGreater(len(ids), 150)
        for pid in ids:
            a, b = progressive_pair(self.db, pid)
            self.assertNotEqual(question_passage(a, pid, self.db),
                                question_passage(b, pid, self.db))
            self.assertIn(a, self.db['pokemon'][str(pid)]['quotes'])
            self.assertIn(b, self.db['pokemon'][str(pid)]['quotes'])
            if a['kind'] not in ('ゲーム内図鑑', 'ゲーム内図鑑の補足'):
                self.assertIs(a.get('quiz_approved'), True)
                self.assertIsNot(a.get('quiz_enabled'), False)

    def test_seeded_session_quizzes_four_unique_options(self):
        for region in ('両方', 'イッシュ', 'パルデア'):
            specs = plan_progressive_session(self.db, region, '全問', seed=20261026)
            self.assertEqual(len(specs), len(progressive_ids(self.db, region)))
            self.assertEqual(len({q['id'] for q in specs}), len(specs))
            for q in specs:
                self.assertEqual(q['mode'], PROGRESSIVE_MODE)
                self.assertEqual(len(q['choices']), 4)
                self.assertEqual(len(set(q['choices'])), 4)
                self.assertIn(q['id'], q['choices'])
                self.assertEqual(len(q['hints']), 2)
                for c in q['choices']:
                    if c != q['id']:
                        shown = ' '.join(question_passage(r, q['id'], self.db)
                                         for r in q['hints'])
                        self.assertNotIn(self.db['pokemon'][str(c)]['name'], shown)

    def test_scoring_and_unavailable_hint_no_penalty(self):
        self.assertEqual(MAX_HINTS, 5)
        self.assertEqual([hint_points(n, list(range(1, n + 1))) for n in range(5)],
                         [5, 4, 3, 2, 1])
        self.assertEqual(hint_points(3, [1]), 4)

    def test_official_profile_parser(self):
        html = '''<html><body><div>検索</div><h2>No.0649 ゲノセクト</h2>
        <div>タイプ：</div><span>むし</span><span>はがね</span><div>高さ：</div><span>1.5m</span>
        <div>重さ：</div>82.5kg<div>特性：</div><p>ダウンロード</p>
        <h2>ダウンロード</h2><p>相手の防御と特防をくらべて……。</p></body></html>'''
        obj = parse_official_zukan_html(html, 'https://zukan.pokemon.co.jp/detail/0649')
        self.assertEqual(obj['types'], ['むし', 'はがね'])
        self.assertEqual(obj['abilities'], ['ダウンロード'])
        self.assertIsNone(parse_official_zukan_html(html, 'https://example.net/detail/0649'))
        self.assertIsNone(parse_official_zukan_html('<html>unknown</html>', 'https://zukan.pokemon.co.jp/detail/0649'))

    def test_official_verified_cases_no_remote_request(self):
        for pid in (649, 909):
            row = self.db['pokemon'][str(pid)]
            self.assertIn('zukan.pokemon.co.jp', official_zukan_url(row))
            profile = get_official_profile(row, lambda _: self.fail('should not fetch'))
            self.assertTrue(profile['types'])
            self.assertTrue(profile['abilities'])


if __name__ == '__main__':
    unittest.main()
