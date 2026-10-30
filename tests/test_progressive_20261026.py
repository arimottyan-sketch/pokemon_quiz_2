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
            originals = self.db['pokemon'][str(pid)]['quotes']
            if a.get('progressive_staged'):
                # Original text is never modified. The two stages are exact
                # progressively longer views of that one source record.
                for stage in (a,b):
                    self.assertTrue(stage['progressive_staged'])
                    self.assertIn({k:v for k,v in stage.items()
                                   if k not in ('progressive_staged','question_text')}, originals)
                self.assertTrue(b['text'].startswith(a['question_text'][:-1]))
            else:
                self.assertIn(a, originals)
                self.assertIn(b, originals)
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

    def test_all_displayed_abilities_two_or_three_and_no_false_positives(self):
        # Simulate the exact text structure of the official page for No.0506.
        html = '''<html><body><div>No.0506 ヨーテリー</div>
        <span>タイプ：</span><span>ノーマル</span><div>高さ：</div><span>0.4m</span>
        <div>特性：</div>
        <div>やるき <span>?</span> 特性</div><h2>やるき</h2>
        <p>やる気を だすことに よって ねむり状態に ならない。</p>
        <div>ものひろい <span>?</span> 特性</div><h2>ものひろい</h2>
        <p>相手の 使った 道具を 拾ってくることが ある。</p>
        <p>ゆうかん かつ しんちょう。</p><div>HP</div>
        <h2>進化</h2><h2>ものひろい</h2>
        </body></html>'''
        obj = parse_official_zukan_html(html, 'https://zukan.pokemon.co.jp/detail/0506')
        self.assertEqual(obj['abilities'], ['やるき', 'ものひろい'])
        self.assertEqual(obj['abilities_scope'], 'official_zukan_displayed')
        self.assertFalse(obj['hidden_abilities_verified'])
        # A third displayed ability is likewise retained (regression test).
        html = html.replace('<p>ゆうかん かつ しんちょう。</p>',
                 '<div>きもったま <span>?</span> 特性</div><h2>きもったま</h2><p>ダメージ。</p>')
        obj = parse_official_zukan_html(html, 'https://zukan.pokemon.co.jp/detail/0506')
        self.assertEqual(obj['abilities'], ['やるき', 'ものひろい', 'きもったま'])

    def test_unverified_hidden_abilities_are_not_fabricated(self):
        for pid in (495, 506, 649, 909):
            row = self.db['pokemon'][str(pid)]
            profile = get_official_profile(row, lambda _: '''<div>No.0495 ツタージャ</div><p>タイプ：</p><b>くさ</b><p>高さ：</p>
                        <b>0.6m</b><p>特性：</p><b>しんりょく</b><h2>しんりょく</h2>
                        <p>HPが減ったとき。 </p><div>HP</div>''')
            self.assertFalse(profile['hidden_abilities_verified'])
        self.assertEqual(get_official_profile(self.db['pokemon']['506'],
                        lambda _: self.fail('should not fetch'))['abilities'],
                         ['やるき', 'ものひろい'])

    def test_official_verified_cases_no_remote_request(self):
        for pid in (649, 909):
            row = self.db['pokemon'][str(pid)]
            self.assertIn('zukan.pokemon.co.jp', official_zukan_url(row))
            profile = get_official_profile(row, lambda _: self.fail('should not fetch'))
            self.assertTrue(profile['types'])
            self.assertTrue(profile['abilities'])


if __name__ == '__main__':
    unittest.main()
