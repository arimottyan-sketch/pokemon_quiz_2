import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from collect_official import parse_official_page, is_fetched

class CollectorTests(unittest.TestCase):
    def doc(self,pokemon):
        return '<html><script id="json-data" type="application/json">'+json.dumps({'pokemon':pokemon},ensure_ascii=False)+'</script></html>'
    def test_parse_two_origins(self):
        html=self.doc({'no':'0494','sub':0,'name':'ビクティニ','text_1':'火が　燃える。　（『ポケットモンスター Ｘ』より）','text_2':'水が　流れる。　（『ポケットモンスター Ｙ』より）','image_m':'https://zukan.pokemon.co.jp/img.png'})
        obj=parse_official_page(html,494,fetched_on='2026-10-21')
        self.assertEqual(len(obj['quotes']),2)
        self.assertEqual(obj['quotes'][0]['text'],'火が　燃える。')
        self.assertEqual(obj['quotes'][0]['original_with_attribution'],'火が　燃える。　（『ポケットモンスター Ｘ』より）')
        self.assertTrue(is_fetched(obj))
    def test_duplicate_texts_not_repeated(self):
        html=self.doc({'no':'0949','sub':0,'name':'リククラゲ','text_1':'同じ文章。　（『ポケットモンスター Ｘ』より）','text_2':'同じ文章。　（『ポケットモンスター Ｘ』より）'})
        obj=parse_official_page(html,949,fetched_on='2026-10-21')
        self.assertEqual(len(obj['quotes']),1)
    def test_reject_number_mismatch(self):
        with self.assertRaisesRegex(ValueError,'一致しません'):
            parse_official_page(self.doc({'no':'0495','sub':0,'name':'x','text_1':'あ。　（『X』より）'}),494,fetched_on='2026-10-21')
    def test_reject_missing_attribution(self):
        with self.assertRaisesRegex(ValueError,'出典表示'):
            parse_official_page(self.doc({'no':'0494','sub':0,'name':'x','text_1':'出典がない。'}),494,fetched_on='2026-10-21')
    def test_reject_missing_script(self):
        with self.assertRaisesRegex(ValueError,'json-data'):
            parse_official_page('<html></html>',494,fetched_on='2026-10-21')

if __name__=='__main__': unittest.main()
