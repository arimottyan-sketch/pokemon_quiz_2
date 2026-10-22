"""Structural behavior tests; official quote text must never be modified in the database."""
import pathlib,sys,unittest,random,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from quiz_engine import (read_db,make_questions,display_quote,missing_ids,REGIONS,PALDEA_FORMS,
                         national_number)
class UIBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = read_db()
    def test_region_contains_four_palden_forms(self):
        self.assertEqual(len(PALDEA_FORMS),4)
        self.assertEqual(len(REGIONS['パルデア']),124)
        self.assertEqual(missing_ids(self.db,'パルデア'),[])
        for key in PALDEA_FORMS:
            self.assertIn(key,REGIONS['パルデア'])
            row=self.db['pokemon'][key]
            self.assertIn(national_number(row),(128,194))
            self.assertTrue(row['pokeapi_slug'])
            self.assertTrue(row['quotes'][0]['url'].startswith('https://zukan.pokemon.co.jp/detail/'))
    def test_form_appears_in_both_modes(self):
        for mode in ['picture','description']:
            questions=make_questions(self.db,'パルデア',mode,seed=314159)
            self.assertEqual(len(questions),124)
            self.assertEqual({q['id'] for q in questions},set(REGIONS['パルデア']))
            for q in questions:
                self.assertEqual(len(q['choices']),4)
                self.assertIn(q['id'],q['choices'])
                self.assertEqual(len(set(q['choices'])),4)
    def test_masks_only_subject(self):
        pokemon=self.db['pokemon']
        self.assertEqual(pokemon['921']['name'],'パモ')
        self.assertEqual(pokemon['922']['name'],'パモット')
        self.assertEqual(
            display_quote('パモとパモットが　遊ぶ。', '921',self.db),
            '？？？とパモットが　遊ぶ。')
        self.assertEqual(
            display_quote('パモとパモットが　遊ぶ。', '922',self.db),
            'パモと？？？が　遊ぶ。')
        self.assertEqual(
            display_quote('コマタナは　キリキザンと　戦う。','624',self.db),
            '？？？は　キリキザンと　戦う。')
        self.assertEqual(
            display_quote('ケンタロスとウパー', '128-paldea-combat',self.db),
            '？？？とウパー')
        self.assertEqual(
            display_quote('ケンタロスとウパー', '194-paldea',self.db),
            'ケンタロスと？？？')
        self.assertEqual(
            display_quote('ブレイズ種の　ケンタロス。','128-paldea-blaze',self.db),
            '？？？の　？？？。')
        self.assertEqual(
            display_quote('ウパーは　ウパーの　仲間。','194-paldea',self.db),
            '？？？は　？？？の　仲間。')
    def test_masks_subject_in_all_choices(self):
        for region in REGIONS:
            for mode in ('picture','description'):
                questions=make_questions(self.db,region,mode,seed=777)
                for q in questions:
                    original=q['quotes'][q['id']]['text']
                    masked=display_quote(original,q['id'],self.db)
                    # No other Pokémon name is masked accidentally if it is a known exact name.
                    if self.db['pokemon'][str(q['id'])]['name'] in original:
                        self.assertIn('？？？',masked)
    def test_verbatim_unchanged_source(self):
        for key in PALDEA_FORMS:
            self.assertEqual(len(self.db['pokemon'][key]['quotes']),2)
            self.assertNotIn('？？？',self.db['pokemon'][key]['quotes'][0]['text'])
    def test_app_picture_choice_markup(self):
        app=(pathlib.Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
        self.assertIn("elif kind in ('description', 'extra_description'):",app)
        self.assertIn('st.columns(2)',app)
        self.assertIn('st.form_submit_button(',app)
        self.assertIn("display_quote(q['quotes'][pid]['text'], pid, db)",app)
        self.assertNotIn('カード・大会情報は過去約3年',app)
if __name__=='__main__':unittest.main()
