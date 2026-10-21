import unittest, csv, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from quiz_engine import read_db, supplementary_records

class Added100Tests(unittest.TestCase):
    def test_added_100_and_official_urls(self):
        base=pathlib.Path(__file__).resolve().parents[1]
        with (base/'ADDED_100_OFFICIAL_VERBATIM.csv').open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),100)
        data=read_db()
        for r in rows:
            self.assertTrue(r['url'].startswith(('https://zukan.pokemon.co.jp/detail/','https://www.pokemon.co.jp/ex/sv/','https://www.tv-tokyo.co.jp/anime/')))
            self.assertIn(r['kind'], ('ゲーム内図鑑の補足','ゲーム公式HP','アニメ公式'))
            matches=[q for q in supplementary_records(data['pokemon'][r['id']]) if q['text']==r['text']]
            self.assertEqual(len(matches),1,(r['id'],r['text']))
            self.assertEqual(matches[0]['source_title'],r['source_title'])
    def test_no_duplicates_within_species(self):
        data=read_db()
        for p in data['pokemon'].values():
            texts=[q['text'] for q in p['quotes']]
            self.assertEqual(len(texts),len(set(texts)),p['name'])
