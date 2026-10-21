import sys, pathlib, unittest, random
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from quiz_engine import read_db,REGIONS,missing_ids,make_questions,supplementary_records
class ReleaseTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.db=read_db()
 def test_all_276_present(self):
  self.assertEqual(sum(len(x) for x in REGIONS.values()),276)
  for region in REGIONS:self.assertEqual(missing_ids(self.db,region),[])
 def test_questions_all_regions_and_modes(self):
  for region in REGIONS:
   for mode in ('picture','description'):
    quiz=make_questions(self.db,region,mode,seed=78)
    self.assertEqual(len(quiz),len(REGIONS[region]))
    for q in quiz:
     self.assertEqual(len(q['choices']),4)
     self.assertEqual(len(set(q['choices'])),4)
     self.assertEqual(len(set(z['text'] for z in q['quotes'].values())),4)
     self.assertIn(q['id'],q['choices'])
 def test_supplementary_filters(self):
  for row in self.db['pokemon'].values():
   for item in supplementary_records(row):self.assertNotEqual(item['kind'],'ゲーム内図鑑')
if __name__=='__main__':unittest.main()
