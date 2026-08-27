import tempfile,unittest
from pathlib import Path
from memory_runtime import engine,post_turn,pre_turn
class MemoryRuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/'memory.db'; self.eng=engine(self.db)
 def tearDown(self): self.tmp.cleanup()
 def test_verified_memory_is_injected(self):
  mid=self.eng.add_candidate('CTS uses evidence gated portable memory',memory_type='configuration',confidence=.95,source_type='user_explicit',primary_domain='CTS',domain_confidence=1.0,domain_verified=False); self.eng.verify_memory(mid); ctx=pre_turn('What memory does CTS use?',self.db); self.assertIn(mid,ctx.verified_memory_ids)
 def test_unverified_relevant_memory_is_blocked(self):
  mid=self.eng.add_candidate('GHV deploys every change automatically',memory_type='configuration',confidence=.7,source_type='strong_inference',primary_domain='GHV',domain_confidence=.8,domain_verified=False); ctx=pre_turn('Does GHV deploy every change automatically?',self.db); self.assertIn(mid,ctx.blocked_memory_ids); self.assertNotIn(mid,ctx.verified_memory_ids)
 def test_post_turn_creates_candidate_not_fact(self):
  result=post_turn('For CTS, I prefer atomic memories.','Understood.',self.db); mem=self.eng.get_memory(result['created_memory_ids'][0]); self.assertEqual(mem['status'],'candidate'); self.assertEqual(mem['primary_domain'],'CTS'); self.assertFalse(bool(mem['domain_verified']))
 def test_ambiguous_domain_stays_unassigned(self):
  result=post_turn('I want this remembered for later.','Okay.',self.db); mid=result['created_memory_ids'][0]; self.assertIsNone(self.eng.get_memory(mid)['primary_domain']); self.assertIn(mid,result['immediate_review_ids'])
 def test_high_impact_requests_review(self):
  result=post_turn('For Homelab, I want production deploys to require approval.','Okay.',self.db); self.assertIn(result['created_memory_ids'][0],result['immediate_review_ids'])
if __name__=='__main__': unittest.main()
