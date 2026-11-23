// Smoke test for the static site: node build/test_site.js
// Loads docs/data.js and docs/app.js without a browser and renders every page.
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const site = path.join(__dirname, "..", "docs");
const sandbox = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(site, "data.js"), "utf8"), sandbox);
const D = sandbox.window.GUIDE_DATA;
const fromJson = JSON.parse(fs.readFileSync(path.join(site, "data.json"), "utf8"));
const G = require(path.join(site, "app.js"));

let failed = 0;
function check(name, ok, detail) {
  if (!ok) { failed++; }
  console.log((ok ? "ok   " : "FAIL ") + name + (detail ? "  " + detail : ""));
}
function text(html) { return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim(); }

check("data.js equals data.json", JSON.stringify(D) === JSON.stringify(fromJson));
const h = D.headline;
check("30 datasets", D.datasets.length === h.datasets, String(D.datasets.length));

const lead = text(G.leadHtml(D));
console.log("     lead: " + lead);
check("lead carries headline numbers", lead.includes(h.period_stated + "건 중 " + h.newer + "건") && lead.includes(h.gap_min + "개월에서 " + h.gap_max + "개월"));
check("facts show reference date", text(G.factsHtml(D)).includes("자료 기준일 " + D.asof));

const all = G.tableHtml(D, {});
check("table lists every dataset", all.count === h.datasets && (all.html.match(/<tr>/g) || []).length === h.datasets + 1);
check("table has column headers and row headers", (all.html.match(/<th scope="col"/g) || []).length === 7 && (all.html.match(/<th scope="row"/g) || []).length === h.datasets);
check("filter newer", G.tableHtml(D, { status: "newer" }).count === h.newer);
check("filter overdue", G.tableHtml(D, { status: "overdue" }).count === h.overdue);
check("filter caution", G.tableHtml(D, { status: "caution" }).count === h.datasets_with_caution);
check("search by name", G.tableHtml(D, { q: "분당" }).count === 1);
check("search by id", G.tableHtml(D, { q: "15114776" }).count === 1);
check("group filter sums to all", D.groups.map((g) => G.tableHtml(D, { group: g }).count).reduce((a, b) => a + b, 0) === h.datasets);
const byDl = G.filterSort(D, { sort: "downloads" });
check("sort by downloads", byDl.every((d, i) => i === 0 || byDl[i - 1].downloads >= d.downloads));
const byGap = G.filterSort(D, { sort: "gap" });
const gv = (d) => (d.period && d.period.gap_months != null ? d.period.gap_months : null);
const firstNull = byGap.findIndex((d) => gv(d) === null);
check("sort by gap keeps 0 and negatives above datasets without a gap",
  byGap.every((d, i) => i === 0 || gv(d) === null || (gv(byGap[i - 1]) !== null && gv(byGap[i - 1]) >= gv(d))) &&
  (firstNull < 0 || byGap.slice(firstNull).every((d) => gv(d) === null)));
check("next check date is after the reference date", !D.next_check || D.next_check > D.asof, String(D.next_check));
check("lead shows the 0-row case", !D.lead_case || lead.includes(D.lead_case.in_end + "행") && lead.includes(D.lead_case.end_col));
check("every period basis is labelled", D.datasets.every((d) => !d.actual || typeof d.actual.basis === "string"));
check("empty result message", G.tableHtml(D, { q: "없는이름" }).html.includes("조건에 맞는 데이터가 없음"));

let cards = 0;
for (const d of D.datasets) {
  const r = G.datasetHtml(D, d.id);
  if (r.title === d.name && r.html.includes(d.url) && r.html.includes("이용 시 주의점")) { cards++; }
  if (/undefined|NaN|\[object/.test(text(r.html))) { check("card text clean " + d.id, false); }
}
check("every dataset card renders", cards === h.datasets, cards + " cards");
const ilsan = G.datasetHtml(D, "15114776").html;
check("repeat range drawn in chart", (ilsan.match(/class="bar rep"/g) || []).length === D.datasets.find((d) => d.id === "15114776").repeat.months);
check("unknown id handled", G.datasetHtml(D, "1").title === "데이터를 찾지 못함");

const sg = G.suggestionsHtml(D);
check("suggestions render", (sg.match(/<section class="sugg"/g) || []).length === D.suggestions.length && D.suggestions.length > 0, D.suggestions.length + " items");
check("copy buttons", (sg.match(/data-copy=/g) || []).length === D.suggestions.length);
check("schedule renders", G.scheduleHtml(D).includes("차기 등록 예정일") || D.schedule.length === 0);
check("changes render", text(G.changesHtml(D)).length > 20);
const mh = G.methodHtml(D);
check("method rule table rows", (mh.match(/dataset\.html\?id=/g) || []).length === h.period_stated + h.other_desc);

const rendered = [G.leadHtml(D), G.factsHtml(D), all.html, sg, G.scheduleHtml(D), G.changesHtml(D), mh].join(" ");
check("no undefined or NaN in pages", !/undefined|NaN|\[object/.test(text(rendered)));

for (const f of ["index.html", "dataset.html", "suggestions.html", "method.html"]) {
  const src = fs.readFileSync(path.join(site, f), "utf8");
  check(f + " is self-contained", !/(src|href)="(https?:)?\/\//.test(src) && src.includes('src="data.js"') && src.includes('src="app.js"') && src.includes('lang="ko"'));
  check(f + " has no digits typed into visible text", !/\d/.test(text(src.replace(/<head>[\s\S]*?<\/head>/, ""))));
}
const css = fs.readFileSync(path.join(site, "style.css"), "utf8");
check("no external requests in css", !/url\(|@import/.test(css));
check("no gradients or shadows that blur", !/gradient|blur\(/.test(css));

// Run the page wiring against a minimal stand-in for the DOM (ids taken from each HTML file).
const appSrc = fs.readFileSync(path.join(site, "app.js"), "utf8");
function runPage(file, search, data) {
  const src = fs.readFileSync(path.join(site, file), "utf8");
  const page = /data-page="([^"]+)"/.exec(src)[1];
  const mk = () => ({ innerHTML: "", textContent: "", value: "", hidden: true, children: [],
    addEventListener() {}, appendChild(c) { this.children.push(c); }, querySelector() { return mk(); },
    getAttribute() { return null; }, setAttribute() {}, scrollIntoView() {} });
  const els = {};
  for (const m of src.matchAll(/id="([^"]+)"/g)) { els[m[1]] = mk(); }
  const document = { readyState: "complete", title: "", body: { getAttribute: (k) => (k === "data-page" ? page : null) },
    getElementById: (id) => els[id] || null, createElement: () => mk(), addEventListener() {} };
  const win = { GUIDE_DATA: data, document, location: { search: search || "", hash: "" }, navigator: {}, setTimeout };
  win.window = win;
  vm.runInNewContext(appSrc, win);
  return { els, document };
}
let p1 = runPage("index.html", "", D);
check("index wiring fills lead, facts, table", p1.els.lead.innerHTML.length > 50 && p1.els.facts.innerHTML.includes(D.asof) && p1.els.table.innerHTML.includes("<table") && p1.els.count.textContent.includes(h.datasets + "종"));
check("index status filter options", p1.els["f-status"].children.length >= 4 && p1.els["f-group"].children.length === D.groups.length);
check("footer shows reference date", p1.els["foot-data"].textContent.includes(D.asof));
p1 = runPage("dataset.html", "?id=15118652", D);
check("dataset wiring", p1.els.app.innerHTML.includes("분당스포츠센터") && p1.document.title.includes("분당스포츠센터"));
p1 = runPage("suggestions.html", "", D);
check("suggestions wiring", p1.els.sugg.innerHTML.length > 100 && p1.els.schedule.innerHTML.length > 20 && p1.els.changes.innerHTML.length > 20 && p1.els.intro.textContent.includes(String(D.suggestions.length)));
p1 = runPage("method.html", "", D);
check("method wiring", p1.els.app.innerHTML.includes("기간 표현 규칙표") && p1.els["app-error"].hidden === true);
p1 = runPage("index.html", "", undefined);
check("missing data shows the error line", p1.els["app-error"].hidden === false);

console.log(failed ? failed + " check(s) failed" : "all checks passed");
process.exit(failed ? 1 : 0);
