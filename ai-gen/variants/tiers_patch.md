# Tiered rendering patch for the gui4gmns.py dashboard TEMPLATE

Problem: draw loop (TEMPLATE ~line 208-215) uses `v=L[2]/maxVol; w=1+5*v` — the ARC max
(39,971 veh) is ~11x the p95, so 99.6% of lit pixels render green (hue stddev 7.3 deg).
Verified fix (render_tiers.py, ARC 145,971 links): 3 tiers + percentile color -> 32 distinct
wide corridors, 69/6/11% green/yellow/red, hue stddev 54.4.

1. Once after M loads (not per frame), classify links. L[2]=volume, L[4]=capacity:
   ```js
   const vols=M.links.filter(L=>L[4]<99000).map(L=>L[2]).sort((a,b)=>a-b);
   const pct=p=>vols[Math.floor(p*(vols.length-1))], p60=pct(0.60), p90=pct(0.90);
   M.links.forEach(L=>L.tier = (L[4]>=99000||L[2]<p60)?0 : (L[2]<p90?1:2));   // connectors => tier 0
   const maj=M.links.filter(L=>L.tier===2).sort((a,b)=>a[2]-b[2]);
   maj.forEach((L,i)=>L.rank=i/Math.max(1,maj.length-1));                     // percentile among majors
   const passes=[M.links.filter(L=>L.tier===0), M.links.filter(L=>L.tier===1), maj];
   ```
2. Replace the single `M.links.forEach(...)` volume-mode draw with three passes, minor first,
   majors last (ascending volume so the hottest links paint on top):
   ```js
   passes.forEach(list=>list.forEach(L=>{ let c,w;
     if(L.tier===0){c='rgb(44,60,52)';  w=0.6;}                               // dim gray-green context
     else if(L.tier===1){c='rgb(58,118,82)'; w=1.5;}                          // muted green arterials
     else {c=ramp(L.rank); w=2.5+3.5*Math.sqrt(L.rank);}                      // green->yellow->red by RANK, 2.5-6px
     ctx.strokeStyle=c; ctx.lineWidth=w; /* existing beginPath/lineTo/stroke */ }));
   ```
3. The existing `ramp(t)` already gives green->yellow->red; feed it `L.rank` (percentile), never
   `L[2]/maxVol`. Keep voc/queue/td modes unchanged, but reuse `L.tier` widths there if desired.

Parameters (validated): tiers at p60/p90 of non-connector volume (ARC: 1,283 / 4,014 veh);
widths 0.6 / 1.5 / 2.5+3.5*sqrt(rank) px; connectors (capacity>=99000) always tier 0.
At high zoom, multiply widths by min(2, zoom/zoom0) so tiers keep their ratio.
