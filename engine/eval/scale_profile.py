import sys,time
sys.path.insert(0,'/app')
from ufinder import config,db
from ufinder.search import Searcher,parse
from ufinder.textutil import match_expr,query_terms
conn=db.connect()
class F:
    id=config.MODEL_ID; dim=1024
s=Searcher(store=None,local=F())
for q in ["w00600 w01500 w03000","w00001 w00002 w00003","zqx000100"]:
    Q=parse(q); w,a=s._where([1],Q)
    t=time.perf_counter(); e=s._focus(conn,q); print(q,'focus',round(time.perf_counter()-t,3),e[:60],flush=True)
    t=time.perf_counter(); h=conn.execute("SELECT rowid AS id, rank AS s FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT 800",(e,)).fetchall(); print(' fts rank',round(time.perf_counter()-t,3),len(h),flush=True)
    t=time.perf_counter(); b=s._bm25(conn,q,w,a); print(' bm25 all',round(time.perf_counter()-t,3),len(b),flush=True)
    t=time.perf_counter(); n=s._names(conn,q,w,a); print(' names',round(time.perf_counter()-t,3),len(n),flush=True)
    for term in query_terms(q)[:3]:
        t=time.perf_counter(); c=conn.execute("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH ?",(f'"{term}"',)).fetchone()[0]; print('  term',term,c,round(time.perf_counter()-t,3),flush=True)
