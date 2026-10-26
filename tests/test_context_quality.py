import unittest,sys,time,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import quiz_engine as q
DB=q.read_db()
ORIG=json.loads((ROOT/'data/source_original_631.json').read_text(encoding='utf-8'))

def question(pid,part):
    return next(r for r in DB['pokemon'][str(pid)]['quotes'] if part in r['text'])

class ContextQualityTests(unittest.TestCase):
    def test_280_slots_and_original_631_unchanged(self):
        self.assertEqual(len(DB['pokemon']),280)
        self.assertEqual(len(q.REGIONS['イッシュ']),156)
        self.assertEqual(len(q.REGIONS['パルデア']),124)
        self.assertEqual(sum(len(v['quotes']) for v in ORIG['pokemon'].values()),631)
        for key,row in ORIG['pokemon'].items():
            for i,old in enumerate(row['quotes']):
                new=DB['pokemon'][key]['quotes'][i]
                for k in ('text','url','kind','source_title'):
                    self.assertEqual(old[k],new[k],(key,i,k))
    def test_five_user_examples_are_contextual_and_not_source_mutations(self):
        for pid,part,required in [
           (617,'快傑ア☆ギルダー','アニメ『ベストウイッシュ』'),
           (632,'葉っぱの服を着たキバゴ','食料と間違え'),
           (922,'パモやパモット','ネモのパモット'),
           (990,'突如球体に変化','真相は不明'),
           (553,'ポケパークの門番','ポケパーク2')]:
            r=question(pid,part)
            self.assertTrue(r['quiz_approved'])
            self.assertIn(required,r['question_text'])
            self.assertIn('？？？',q.question_passage(r,pid,DB))
    def test_works_as_quiz_standalone(self):
        for key,row in DB['pokemon'].items():
            for r in q.eligible_extra(row):
                s=r.get('question_text') or r['text']
                self.assertGreaterEqual(len(s),18,(key,s))
                self.assertTrue(s.endswith(('。','！','？')),(key,s))
                self.assertFalse(re.match(r'^(その|ここ|どうやら|突如)',s),(key,s))
                self.assertFalse(s.endswith(('おり','技です。')),(key,s))
    def test_all_question_sets_have_unique_choices(self):
        for mode in ('extra_mix','extra_picture','extra_description','mix','description','picture'):
            for region in ('イッシュ','パルデア','両方'):
                planned=q.plan_session(DB,region,mode,'全問',seed=41)
                self.assertEqual(len(planned),len(set((str(x['id']),x.get('source_record_index',-1)) for x in planned)))
                for x in planned:
                    self.assertEqual(len(x['choices']),4)
                    self.assertEqual(len(set(map(str,x['choices']))),4)
                    self.assertIn(x['id'],x['choices'])
                    if x['mode']=='extra_picture':
                        all_text=[q.question_passage(x['quotes'][p],p,DB) for p in x['choices']]
                        self.assertEqual(len(all_text),4)
        self.assertGreaterEqual(q.extra_record_count(DB,'両方'),100)
    def test_ui_kept_prior_features_with_speed_switch(self):
        app=(ROOT/'app.py').read_text(encoding='utf-8')
        self.assertIn("st.title('ポケモンクイズ')",app)
        self.assertNotIn('適用範囲：',app)
        self.assertIn('正しい選択肢：',app)
        self.assertIn('軽量表示',app)
        self.assertIn('light_mode',app)
    def test_mega_or_special_images_not_incorrectly_substituted(self):
        for pid,needle in [(604,'遊泳するスピード'),(998,'みぞおちグリップ'),(500,'蛇矛の先端')]:
            rec=question(pid,needle)
            self.assertTrue(rec.get('require_special_form_image'))
        for task in q.plan_session(DB,'両方','extra_mix','全問',seed=7):
            if task['quotes'][task['id']].get('require_special_form_image'):
                self.assertEqual(task['mode'],'extra_description')
                self.assertTrue(task.get('force_text_choices'))

if __name__=='__main__':unittest.main()
