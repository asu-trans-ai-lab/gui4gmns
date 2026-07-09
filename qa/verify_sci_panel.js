#!/usr/bin/env node
// verify_sci_panel.js -- executes the REAL computeSCI() function extracted from a generated
// dashboard.html against that dashboard's own generated layer files, so checkpoint L (data-quality
// audit) is tested against production code, not a reimplementation that could drift or be
// transcribed wrong. See qa/AI_GUIDE_gui4gmns.md checkpoint L and qa/TEST_PLAN.md method M-A.
//
// Usage: node qa/verify_sci_panel.js <gmns_folder>
// Prints each of the 7 SCI checks' pass/fail/na + stat; exits 1 if any active (non-n/a) check fails.

const fs = require('fs');
const path = require('path');

function loadLayer(folder, key, file) {
  const p = path.join(folder, 'dashboard_layers', file);
  if (!fs.existsSync(p)) return null;
  const js = fs.readFileSync(p, 'utf8');
  const tok = `NX.${key}=`;
  const i = js.indexOf(tok);
  if (i < 0) return null;
  let s = js.slice(i + tok.length);
  s = s.slice(0, s.lastIndexOf('}') + 1);
  return JSON.parse(s);
}

function buildM(folder) {
  const net = loadLayer(folder, 'network', 'network.js') || { meta: {}, nodes: [], links: [] };
  const moe = loadLayer(folder, 'moe', 'moe.js') || {};
  const td = loadLayer(folder, 'td', 'td.js') || { bins: [], td: {} };
  const trajs = loadLayer(folder, 'trajs', 'trajectories.js') || {};
  const run = loadLayer(folder, 'run', 'run.js') || { run: null, paths: [] };
  // replicate the dashboard's own inline loader: splice [vol,queue] from moe.js into each network
  // link at index 2, exactly as `const DATA=(function(){...})()` does in the generated HTML.
  const links = net.links.map((L) => {
    const m = moe[String(L[0])] || [0, 0];
    const copy = L.slice();
    copy.splice(2, 0, m[0], m[1]);
    return copy;
  });
  return { links, nodes: net.nodes, bins: td.bins, td: td.td, trajs, run: run.run };
}

function extractComputeSCI(folder) {
  const html = fs.readFileSync(path.join(folder, 'dashboard.html'), 'utf8');
  const start = html.indexOf('function computeSCI(){');
  const end = html.indexOf('function renderSci(){', start);
  if (start < 0 || end < 0) throw new Error('computeSCI() not found in dashboard.html -- regenerate first');
  return html.slice(start, end);
}

function main() {
  const folder = process.argv[2];
  if (!folder) { console.error('usage: node verify_sci_panel.js <gmns_folder>'); process.exit(2); }
  const M = buildM(folder);
  const src = extractComputeSCI(folder);
  const fn = new Function('M', src + '\nreturn computeSCI();');
  const results = fn(M);
  let nfail = 0, nna = 0;
  console.log(`SCI physics panel -- ${folder}`);
  for (const r of results) {
    const status = r.na ? 'NA' : r.pass ? 'PASS' : 'FAIL';
    if (status === 'FAIL') nfail++; else if (status === 'NA') nna++;
    console.log(`  [${r.id}] ${r.desc.padEnd(52)} ${status.padEnd(4)} ${r.stat}${r.fail ? '  -- ' + r.fail : ''}`);
  }
  console.log(`\n${results.length - nna - nfail} pass, ${nfail} fail, ${nna} n/a  (of ${results.length} checks)`);
  process.exit(nfail ? 1 : 0);
}
main();
