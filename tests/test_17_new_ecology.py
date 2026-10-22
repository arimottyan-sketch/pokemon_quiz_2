import unittest, pathlib, csv, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from quiz_engine import read_db, make_questions, supplementary_records
from staff_learning import plan_session

class EcologyTest(unittest.TestCase):
    def test_new_verbatim_entries_and_quiz(self):
        home = pathlib.Path(__file__).resolve().parents[1]
        with (home/'NEW_VERBATIM_ECOLOGY_20261022.csv').open(encoding='utf-8-sig',newline='') as f:
            records=list(csv.DictReader(f))
        self.assertEqual(len(records), 17)
        self.assertEqual(len({(r['id'],r['text']) for r in records}),17)
        data=read_db()
        self.assertGreaterEqual(sum(len(p['quotes']) for p in data['pokemon'].values()),434)
        for r in records:
            match=[q for q in supplementary_records(data['pokemon'][r['id']]) if q['text']==r['text']]
            self.assertEqual(len(match),1)
            self.assertEqual(match[0]['url'],r['url'])
            self.assertEqual(match[0]['source_title'],r['source_title'])
            self.assertEqual(match[0]['quote_type'],'direct_verbatim_excerpt')
            region='イッシュ' if int(r['id'])<650 else 'パルデア'
            q=make_questions(data,region,'extra_description',ids=[int(r['id'])],seed=1)
            self.assertEqual(q[0]['answer'],int(r['id']))
        for region in ('イッシュ','パルデア'):
            self.assertEqual(len(plan_session(data,region,'mix',10,seed=123)),10)

if __name__=='__main__': unittest.main()
