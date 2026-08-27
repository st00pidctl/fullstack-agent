#!/usr/bin/env python3
"""Provider-neutral live-turn bridge for the portable memory graph."""
from __future__ import annotations
import json,re
from dataclasses import dataclass
from pathlib import Path
from memory_engine import MemoryEngine
ROOT=Path(__file__).resolve().parent
DEFAULT_DB=ROOT/"memory"/"memory.db"
SCHEMA=ROOT/"memory"/"schema.sql"
DEFAULT_DOMAINS=("CTS","GHV","GS Tech","IQVIA","Personal","Homelab")
TOKEN_RE=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,}")
DOMAIN_HINTS={"CTS":("cts","cassady tech","cassady tech solutions"),"GHV":("ghv","greenhorn valley tech","greenhorn"),"GS Tech":("gs tech","gstek"),"IQVIA":("iqvia",),"Homelab":("homelab","proxmox","pve","jellyfin","tailscale","vm","server"),"Personal":("personal","family","home","wife","son","daughter")}
HIGH_IMPACT_TERMS=("password","credential","delete","remove","deploy","publish","merge","purchase","pay","invoice","deadline","contract","security","production")
@dataclass(frozen=True)
class TurnContext:
    prompt_context:str; domain:str|None; domain_confidence:float; verified_memory_ids:tuple[str,...]; blocked_memory_ids:tuple[str,...]; clarification:str|None; audit_due:bool
    def as_dict(self): return {"prompt_context":self.prompt_context,"domain":self.domain,"domain_confidence":self.domain_confidence,"verified_memory_ids":list(self.verified_memory_ids),"blocked_memory_ids":list(self.blocked_memory_ids),"clarification":self.clarification,"audit_due":self.audit_due}
def engine(db_path=None):
    eng=MemoryEngine(db_path or DEFAULT_DB,SCHEMA); eng.initialize()
    for domain in DEFAULT_DOMAINS: eng.add_domain(domain)
    return eng
def _tokens(text): return {m.group(0).lower() for m in TOKEN_RE.finditer(text)}
def classify_domain(text):
    lower=text.lower(); scored=[]
    for domain,hints in DOMAIN_HINTS.items():
        score=sum(1 for hint in hints if hint in lower)
        if score: scored.append((score,domain))
    if not scored:return None,0.0
    scored.sort(reverse=True); best_score,best=scored[0]
    if len(scored)>1 and scored[1][0]==best_score:return None,0.45
    return best,min(1.0,0.75+0.1*(best_score-1))
def _candidate_rows(eng,utterance,domain,limit=12):
    q=_tokens(utterance)
    if not q:return []
    with eng.connect() as conn: rows=conn.execute("SELECT id,claim,status,primary_domain,domain_verified,confidence,relevance,freshness,impact,likely_action_driver,memory_type FROM memories WHERE status IN ('verified','candidate','disputed') ORDER BY updated_at DESC LIMIT 250").fetchall()
    ranked=[]
    for row in rows:
        overlap=len(q&_tokens(row['claim']))
        if overlap: ranked.append((overlap*4+(2 if domain and row['primary_domain']==domain else 0)+float(row['relevance']),row))
    ranked.sort(key=lambda x:x[0],reverse=True); return [r for _,r in ranked[:limit]]
def pre_turn(utterance,db_path=None):
    eng=engine(db_path); domain,dc=classify_domain(utterance); rows=_candidate_rows(eng,utterance,domain); verified=[]; blocked=[]
    for row in rows:
        (verified if eng.point_of_use_gate([row['id']]).allowed else blocked).append(row)
    lines=["PORTABLE MEMORY CONTEXT (shell-owned, evidence-gated):",f"Primary domain for this turn: {domain or 'UNRESOLVED'} (confidence {dc:.2f}).","Treat only VERIFIED items below as durable facts. Never promote inference by repetition."]
    if verified:
        lines.append("VERIFIED RELEVANT MEMORY:"); lines += [f"- [{r['id']}] ({r['primary_domain']}) {r['claim']}" for r in verified[:8]]
    else: lines.append("VERIFIED RELEVANT MEMORY: none retrieved.")
    clarification=None
    if blocked:
        lines.append("UNVERIFIED/DISPUTED MEMORY: do not rely on these claims without user confirmation."); lines += [f"- [{r['id']}] {r['claim']}" for r in blocked[:5]]; clarification="Relevant memory exists but is not verified. Confirm it before relying on it."
    if domain is None: lines.append("DOMAIN RULE: durable memory from this turn must remain candidate until one primary domain is resolved.")
    audit=eng.audit_due()
    if audit.get('due'): lines.append("MEMORY AUDIT DUE: surface this naturally when it will not derail an urgent task.")
    return TurnContext("\n".join(lines),domain,dc,tuple(r['id'] for r in verified),tuple(r['id'] for r in blocked),clarification,bool(audit.get('due')))
def _atomic_user_claims(utterance):
    text=" ".join(utterance.strip().split()); durable=[]; markers=("i want ","i need ","i prefer ","i use ","i have ","i am ","i'm ","we use ","we have ","we are ","my ","our ","the decision is ")
    for sentence in re.split(r"(?<=[.!?])\s+",text):
        lower=sentence.lower().strip()
        if 8<=len(sentence)<=500 and any(m in lower for m in markers): durable.append(sentence.strip())
    return durable[:6]
def post_turn(utterance,response,db_path=None):
    eng=engine(db_path); domain,dc=classify_domain(utterance); created=[]; immediate=[]; high=any(t in utterance.lower() for t in HIGH_IMPACT_TERMS)
    for claim in _atomic_user_claims(utterance):
        mtype="preference" if any(x in claim.lower() for x in ("i want","i prefer","i need")) else "stable_fact"
        mid=eng.add_candidate(claim,memory_type=mtype,confidence=.72,source_type="user_explicit",primary_domain=domain,domain_confidence=dc if domain else None,domain_verified=False,source_ref="live_turn:user",relevance=.65,freshness=1.0,impact="high" if high else "normal",likely_action_driver=high,metadata={"capture":"live_turn","assistant_response_present":bool(response.strip())})
        created.append(mid)
        if high or domain is None: immediate.append(mid)
    return {"created_memory_ids":created,"immediate_review_ids":immediate,"domain":domain,"domain_confidence":dc,"audit":eng.audit_due()}
def main():
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=('pre','post')); p.add_argument('--utterance',required=True); p.add_argument('--response',default=''); p.add_argument('--db'); a=p.parse_args(); result=pre_turn(a.utterance,a.db).as_dict() if a.mode=='pre' else post_turn(a.utterance,a.response,a.db); print(json.dumps(result,sort_keys=True))
if __name__=='__main__': main()
