import unittest,csv,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from quiz_engine import read_db,make_questions,display_quote,supplementary_records
from staff_learning import plan_session
class NicheVerifiedTest(unittest.TestCase):
 def test_new_official_entries(self):
  root=pathlib.Path(__file__).resolve().parents[1]
  db=read_db()
  with (root/'NEW_NICHE_OFFICIAL_20261022.csv').open(encoding='utf-8-sig',newline='') as f:
   rows=list(csv.DictReader(f))
  self.assertEqual(len(rows),12)
  self.assertEqual(sum(len(x['quotes']) for x in db['pokemon'].values()),446)
  for r in rows:
   row=db['pokemon'][r['図鑑番号']]
   self.assertEqual(row['name'],r['ポケモン'])
   matches=[q for q in supplementary_records(row) if q['text']==r['公式原文（抜粋）']]
   self.assertEqual(len(matches),1,(r['図鑑番号'],r['ポケモン']))
   q=matches[0]
   self.assertEqual(q['url'],r['公式URL'])
   self.assertEqual(q['source_title'],r['公式掲載元'])
   self.assertEqual(q['source_scope'],r['適用範囲'])
   self.assertEqual(q['quote_type'],'official_verbatim_excerpt')
   self.assertEqual(q['verification_method'],'official_website_text_read_via_web_tool')
   self.assertNotEqual(display_quote(q['text'],int(r['図鑑番号']),db),q['text']) if row['name'] in q['text'] else None
   region='イッシュ' if int(r['図鑑番号'])<650 else 'パルデア'
   self.assertEqual(make_questions(db,region,'extra_description',ids=[int(r['図鑑番号'])],seed=4)[0]['id'],int(r['図鑑番号']))
 def test_session_mix(self):
  db=read_db()
  for region in ['イッシュ','パルデア','両方']:
   self.assertEqual(len(plan_session(db,region,'mix',10,seed=42)),10)
if __name__=='__main__':unittest.main()
