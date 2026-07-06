# LOD + filter layers + data-check overlay — patch for `ai-gen/gui4gmns.py`

Validated on ARC Atlanta (145,971 links) by `variants/render_lod.py`.
Measured: drawing everything = 8.7% pixel ink (unreadable soup); tier-1-only
overview = 3.4% ink from 13.5% of links and reads as a clean freeway/arterial
skeleton. Link record gains a 7th field: **tier** (index 6).

Tier definition (percentiles of `capacity*lanes`, centroid connectors excluded):

| tier | rule (ARC values)            | count  | show when            |
|------|------------------------------|--------|----------------------|
| 1    | top 15%  (cap*lanes >= 2200) | 19,724 | always               |
| 2    | top 50%  (cap*lanes >= 1000) | 46,751 | zoom >= 2.5          |
| 3    | rest of real roads           | 52,212 | zoom >= 8            |
| 4    | centroid connectors (cap>=50000) | 27,284 | only when LOD off |

## 1. Python generator — tier precomputation

In `load()`, immediately AFTER the link loop (after the line
`if miss_geom: ck.append(f"WARN {miss_geom} links ...")`, ~line 72), add:

```python
    # ---- LOD tier precomputation: index 6 of each link record ----
    # L = [lid, poly, vol, q, cap(=capacity*lanes), len_mi, tier]
    caps = sorted((L[4] for L in D["links"] if L[4] < 50000), reverse=True)
    thr1 = caps[max(0, int(len(caps) * 0.15) - 1)] if caps else 0   # top 15%
    thr2 = caps[max(0, int(len(caps) * 0.50) - 1)] if caps else 0   # top 50%
    for L in D["links"]:
        L.append(4 if L[4] >= 50000 else                 # centroid connector
                 1 if L[4] >= thr1 else 2 if L[4] >= thr2 else 3)
    ck.append(f"LOD tiers: t1 cap*lanes>={thr1:.0f}, t2>={thr2:.0f}, "
              f"connectors={sum(1 for L in D['links'] if L[6] == 4)}")
```

(`L[4]` is already `capacity * max(1, lanes)` — see line 69 — so the
`>= 50000` test cleanly isolates the capacity-99999 connectors.)

## 2. Template controls — add to the `#bar` div

In `TEMPLATE`, after the existing basemap label
(`<label style="color:#8a94a3"><input type="checkbox" id="base" checked onchange="draw()"> basemap</label>`), add:

```html
<label style="color:#8a94a3"><input type="checkbox" id="lod" checked> LOD</label>
<label style="color:#8a94a3"><input type="checkbox" id="checks_layer"> checks</label>
<label style="color:#8a94a3">min vol <input type="range" id="minvol" min="0" max="100" value="0" style="width:110px"></label>
```

(No `onchange` needed — `draw()` runs every animation frame.)

## 3. Template draw loop — zoom-threshold + min-volume filter

Replace the line
`M.links.forEach(L=>{let v=0,w=1;`
with:

```js
 const lodOn=document.getElementById('lod').checked;
 const maxTier=!lodOn?4:zoom<2.5?1:zoom<8?2:3;  // connectors (tier 4) only when LOD off
 const vmin=Math.pow(+document.getElementById('minvol').value/100,2)*maxVol; // quadratic slider: fine control at low end
 let drawn=0;
 M.links.forEach(L=>{if(L[6]>maxTier||L[2]<vmin)return;drawn++;let v=0,w=1;
```

Optionally surface `drawn` in the HUD:
`document.getElementById('clock').textContent += \`  ·  ${drawn.toLocaleString()} links\`;`

## 4. Template checks layer — magenta suspicious links

Immediately AFTER the `M.links.forEach(...)` MOE loop closes
(`...L[1].forEach((p,i)=>{...});ctx.stroke();});`) and BEFORE the
trajectory block (`const lk={};`), add:

```js
 if(document.getElementById('checks_layer').checked){
  ctx.lineCap='round';
  M.links.forEach(L=>{if(L[2]>0)return;
   if(L[4]>=50000){ctx.strokeStyle='#ff00c8';ctx.lineWidth=2;}   // zero-flow centroid connector
   else if(L[6]===1){ctx.strokeStyle='#ff9600';ctx.lineWidth=3;} // zero-volume tier-1 real road
   else return;
   ctx.beginPath();
   L[1].forEach((p,i)=>{const s=W(p[0],p[1]);i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]);});
   ctx.stroke();});}
```

Note the checks layer intentionally ignores the LOD/min-vol filters: data
problems must stay visible at every zoom.

## 5. Calibration note (why not `capacity >= 3000*lanes`)

In ARC, `capacity` is per-lane (median cap*lanes = 1000; 99th pct = 8000;
real-road max per-lane values ~2000-4100). The literal
`volume==0 && capacity>=3000*lanes` check fires on **exactly the 1,293
capacity-99999 centroid connectors (479 lane-mi) and zero real roads**.
Keep it as the "dead zone / unused connector" check (magenta), and add the
tier-based check `volume==0 && tier==1` for real roads (27 links, 8.2
lane-mi on ARC — orange). Both are implemented above via `L[4]>=50000` and
`L[6]===1`.

## Recommended thresholds (ARC-validated)

- tier 1 cutoff: **top 15%** of cap*lanes (ARC: >= 2200) — 3.4% pixel ink at full extent.
- tier 2 cutoff: **top 50%** (ARC: >= 1000) — 6.9% ink on a ~30x30 km regional zoom.
- zoom breakpoints: **z<2.5 tier 1; z<8 tiers 1-2; z>=8 all real roads**; connectors never auto-drawn.
- min-vol slider: quadratic mapping of 0-100 to 0-maxVol.
- keep total pixel coverage under ~7% per view; 8.7%+ (draw-everything) is the clutter regime.
