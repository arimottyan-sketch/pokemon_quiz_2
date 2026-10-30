import unittest,sys,csv,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from quiz_engine import read_db,source_is_allowed
from progressive_quiz import progressive_ids, progressive_pair, get_official_profile
class OfficialOnly(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.db=read_db()
 def test_new_sources(self):
  with (ROOT/'data/POKEMON_OFFICIAL_NEW_8_20261028.csv').open(encoding='utf-8-sig') as f:
   for r in csv.DictReader(f):
    hits=[x for x in self.db['pokemon'][r['id']]['quotes'] if x['text']==r['text'] and x['url']==r['url']]
    self.assertEqual(len(hits),1,r['id']);self.assertTrue(source_is_allowed(hits[0]))
 def test_coverage(self):
  self.assertEqual(len(progressive_ids(self.db,'両方')),280)
  self.assertNotIn(512,[p for p in progressive_ids(self.db,'両方') if progressive_pair(self.db,p)[1].get('progressive_staged')])
  # Legacy snapshot expected 9; the new verified official Liepard card resolves 1.
  self.assertEqual(len([p for p in progressive_ids(self.db,'両方') if progressive_pair(self.db,p)[1].get('progressive_staged')]),0)
 def test_no_non_official_networks(self):
  for f in ROOT.glob('*.py'):
   text=f.read_text(encoding='utf-8');self.assertNotIn('yakkun.com',text);self.assertNotIn('pokeapi.co',text)
 def test_official_profile_no_supplement(self):
  row=self.db['pokemon']['514']
  p=get_official_profile(row,lambda u:'')
  self.assertTrue(p is None or 'ability_reference_url' not in p)
