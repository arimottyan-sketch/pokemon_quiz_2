import unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import quiz_engine as q
DB=q.read_db()
EXPECTED={
  'film2013_genesect_homesick':('649','映画『神速のゲノセクト ミュウツー覚醒』'),
  'film2013_genesect_four_cassettes':('649','赤い個体以外の４体'),
  'film2012_meloetta_moon_concert':('648','映画短編『メロエッタのキラキラリサイタル』'),
}
class MovieNew3Tests(unittest.TestCase):
    def test_sources_and_scopes(self):
        for key,(pid,needle) in EXPECTED.items():
            records=[r for r in DB['pokemon'][pid]['quotes'] if r.get('topic_key')==key]
            self.assertEqual(len(records),1)
            rec=records[0]
            self.assertIn(needle,rec['question_text'])
            self.assertTrue(rec['source_scope'])
            self.assertTrue(rec['quiz_approved'])
            self.assertTrue(rec['verified_on'])
            self.assertTrue(rec['url'].startswith('https://www.pokemon.co.jp/tv_movie/movie/'))
            self.assertTrue(q.is_standalone_question(rec))
            self.assertNotIn(DB['pokemon'][pid]['name'],q.question_passage(rec,int(pid),DB))
    def test_new_three_appear_in_both_ways(self):
        for mode in ('extra_description','extra_picture','extra_mix'):
            for seed in (3,31,123):
                tasks=q.plan_session(DB,'両方',mode,'全問',seed=seed)
                found={t['quotes'][t['id']].get('topic_key'):t for t in tasks if t['quotes'][t['id']].get('topic_key') in EXPECTED}
                self.assertEqual(set(found),set(EXPECTED))
                for key,t in found.items():
                    self.assertEqual(len(t['choices']),4)
                    self.assertEqual(len(set(map(str,t['choices']))),4)
                    self.assertEqual(t['id'],int(EXPECTED[key][0]))
                    self.assertIn(t['id'],t['choices'])
    def test_source_originals_exact(self):
        expected={
        'film2013_genesect_homesick':'昔とあまりにも違う世界にとまどい、「ウチニカエリタイ……」と、テレパシーでサトシたちに語りかけてくるゲノセクト。',
        'film2013_genesect_four_cassettes':'４体それぞれの背中の砲台にセットされているカセットが異なる。',
        'film2012_meloetta_moon_concert':'満月が「ルナトーン岩」の上に来る時、幻のポケモン、メロエッタのリサイタルが始まるよ。',
        }
        for pid,row in DB['pokemon'].items():
            for rec in row['quotes']:
                if rec.get('topic_key') in expected:
                    self.assertEqual(rec['text'],expected[rec['topic_key']])
if __name__=='__main__': unittest.main()
