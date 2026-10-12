import csv,sys,collections,re,json
def mib(s):
    v,u=re.match(r"([\d.]+)(\w+)",s.split('/')[0].strip()).groups(); v=float(v)
    return v*{'KiB':1/1024,'MiB':1,'GiB':1024,'B':1/1048576}[u]
out={}
for f in ["stats_core_idle","stats_core_load","stats_full_idle","stats_full_load"]:
    d=collections.defaultdict(lambda:[[],[]])
    for n,c,m in csv.reader(open(f+".csv")):
        d[n][0].append(float(c.strip('%'))); d[n][1].append(mib(m))
    per={n:{"cpu_pct_mean":sum(v[0])/len(v[0]),"cpu_pct_max":max(v[0]),"mem_mib_mean":sum(v[1])/len(v[1])} for n,v in d.items()}
    out[f]={"containers":per,"n_containers":len(per),"total_cpu_pct_mean":sum(p["cpu_pct_mean"] for p in per.values()),"total_mem_mib_mean":sum(p["mem_mib_mean"] for p in per.values())}
json.dump(out,open("stats_summary.json","w"),indent=1)
for f,v in out.items():
    print(f, v["n_containers"], round(v["total_cpu_pct_mean"],1), round(v["total_mem_mib_mean"]))
    for n,p in sorted(v["containers"].items()): print("   ",n,round(p["cpu_pct_mean"],1),round(p["mem_mib_mean"]))
