# contrast_patch.md — COLOR SCIENCE patch for `ai-gen/gui4gmns.py` TEMPLATE

Goal: make the 145,971-link ARC Atlanta network readable over OSM / satellite
basemaps. Validated offscreen (PySide6) by `variants/render_contrast.py`;
see measured metrics at the bottom. Line numbers refer to `ai-gen/gui4gmns.py`
as of this test.

## Why the current TEMPLATE fails

1. `v = L[2]/maxVol` (line 209) normalizes by the outlier max (39,971 veh).
   ARC volumes: p25=198, p50=639, p85=2,706, p99=14,412. So 98% of links get
   v < 0.07 -> identical green; only the top ~2% ever leave green.
2. 1px unhaloed strokes at globalAlpha-composited tile brightness vanish into
   OSM road casings and satellite texture (measured local contrast 0.123 on OSM).

## Patch 1 — anchored LOG volume ramp (p25 -> 0, p99 -> 1)

After line 186 (`M.links.forEach(L=>{maxVol=...})`) add:

```js
const vs=M.links.map(L=>L[2]).filter(v=>v>0).sort((a,b)=>a-b);
const q=p=>vs.length?vs[Math.min(vs.length-1,Math.floor(p*vs.length))]:1;
const LO=Math.log1p(q(0.25)),HI=Math.log1p(q(0.99));          // anchor: p25..p99
const vlog=x=>Math.max(0,Math.min(1,(Math.log1p(x)-LO)/(HI-LO)));
M.links.sort((a,b)=>a[2]-b[2]);                               // low volume first -> hot links on top
```

Replace line 209:

```js
if(mode==='volume'){v=L[2]/maxVol;w=1+5*v;}
```

with:

```js
if(mode==='volume'){v=vlog(L[2]);w=1+2.2*v;}
```

The `ramp(t)` at line 200 is unchanged. IMPORTANT: do NOT use the naive
`log1p(vol)/log1p(p99)` (0-anchored) — tested, it saturates the map the other
way (98.2% of network pixels non-green; everything reads orange/red). The p25
low anchor puts the median (639) at t≈0.27 (green), p85 (2,706) at t≈0.61
(orange), p99+ at red — measured 57.4% red+yellow pixel share with 100% of
high-volume-link pixels distinguishable.

## Patch 2 — dark halo casing (two-pass stroke)

Replace the single link loop (lines 208–215) with a factored MOE function and
two passes — casing first, color second (per-link interleaving leaves gaps at
junction overlaps):

```js
ctx.lineCap='round';ctx.lineJoin='round';
const moe=L=>{let v=0,w=1;
 if(mode==='volume'){v=vlog(L[2]);w=1+2.2*v;}
 else if(mode==='voc'){v=Math.min(1,L[2]/(L[4]*8||1));w=1+4*v;}
 else if(mode==='queue'){v=L[3]/maxQ;w=1+5*v;}
 else{const d=(M.td[L[0]]||{})[b];const inf=d?d[0]:0,q2=d?d[1]:0;
  v=q2>0?0.55+0.45*Math.min(1,q2/60):Math.min(1,inf*4/(L[4]||1800));w=1+4*Math.min(1,inf/450);}
 return[v,w];};
const seg=(L,w,style)=>{ctx.strokeStyle=style;ctx.lineWidth=w;ctx.beginPath();
 L[1].forEach((p,i)=>{const s=W(p[0],p[1]);i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]);});ctx.stroke();};
if(document.getElementById('base').checked)                     // casing only needed over imagery
 M.links.forEach(L=>{const[,w]=moe(L);seg(L,w+3,'rgba(0,0,0,0.71)');});  // 1.5px halo each side, a=180/255
M.links.forEach(L=>{const[v,w]=moe(L);seg(L,w,ramp(v));});
```

Cost: one extra stroke pass (~2x draw time; offscreen QPainter equivalent was
19.7s vs 9.1s for 145,971 links at 1600x1000 — acceptable; skip the casing pass
below a zoom threshold if interactivity suffers).

## Patch 3 — background dim + desaturate

Replace lines 205–206 (`ctx.globalAlpha=.55; drawImage...`) with:

```js
if(document.getElementById('base').checked)tiles.forEach(([im,x0,x1,y0,y1])=>{if(!im.complete||!im.naturalWidth)return;
 const a=W(x0,y1),b2=W(x1,y0);
 ctx.filter='saturate(40%)';               // 60% desaturation (ignored by very old browsers -> safe)
 ctx.globalAlpha=.45;                      // 55% dim: composites toward the #101418 page fill
 ctx.drawImage(im,a[0],a[1],b2[0]-a[0],b2[1]-a[1]);
 ctx.globalAlpha=1;ctx.filter='none';});
```

`globalAlpha=.45` over the existing `#101418` fillRect (line 203) is exactly a
55% dim toward near-black; `saturate(40%)` kills the OSM landuse greens/tans
that camouflage the low-volume green links.

## Patch 4 — satellite tile source

The Python side of `gui4gmns.py` (lines 118–126) already embeds ESRI
World_Imagery when `basemap="satellite"`. For the live-fetch fallback in JS,
replace line 198:

```js
img.src=`https://tile.openstreetmap.org/${z}/${tx}/${ty}.png`;
```

with:

```js
img.src=(DATA.meta.basemap==='satellite')
 ?`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${ty}/${tx}`  // NOTE z/y/x
 :`https://tile.openstreetmap.org/${z}/${tx}/${ty}.png`;
```

(and pass `basemap` through `D["meta"]`). Satellite needs no extra dimming
beyond Patch 3 — Atlanta imagery is dark forest; the same 55%/40% values gave
the best measured contrast of all four variants (0.591).

## Recommended parameters (as measured)

| parameter                | value |
|--------------------------|-------|
| volume scale             | `v=(log1p(vol)-log1p(p25))/(log1p(p99)-log1p(p25))`, clamped [0,1] (natural log; p25 low anchor is what prevents all-red saturation) |
| p99 clamp                | yes — outliers above p99 all map to full red |
| line width               | `1 + 2.2*v` px (was `1 + 5*v` — with log v, 5x over-inks 145k links) |
| casing                   | `#000` at alpha 180/255 (`rgba(0,0,0,0.71)`), +1.5px each side (`lineWidth = w+3`), round cap/join, full pass under the color pass |
| OSM dim                  | 55% toward `#101418` (`globalAlpha=.45` over dark fill) |
| OSM desaturation         | 60% (`ctx.filter='saturate(40%)'`) |
| satellite dim/desat      | same 55% / 60% |
| draw order               | sort links by volume ascending (hot links stroke last/on top) |

## Measured results (render_contrast.py, 1600x1000, z10, 54 tiles, seed 42)

| image             | mean local contrast | % class distinguishable | % red+yellow overall |
|-------------------|--------------------:|------------------------:|---------------------:|
| arc_osm_plain.png |               0.123 |                    31.4 |                  5.4 |
| arc_osm_tuned.png |               0.311 |                   100.0 |                 57.4 |
| arc_sat_plain.png |               0.468 |                    31.3 |                  5.4 |
| arc_sat_tuned.png |               0.591 |                   100.0 |                 57.4 |

- mean local contrast: |luminance(link px) − mean luminance of non-network px
  within 5px|, /255, over 2000 random link pixels.
- % class distinguishable: of pixels on links with vol ≥ p85 (2,706), share
  whose displayed hue is clearly non-green (hue<95° or ≥300°, sat>0.25).
- plain = current TEMPLATE behaviour (linear v, no casing, 40% dim).

Tuned OSM = 2.5x the local contrast of plain OSM and takes yellow/red class
visibility from 31% to 100%. On satellite the plain render "pops" in luminance
(bright green on dark forest) but still hides all volume classes — the log
ramp, not the halo, is what fixes classification; the halo is what fixes OSM.
