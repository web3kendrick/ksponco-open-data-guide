/* 한국체육산업개발 공공데이터 이용 안내
   Every number on the pages comes from data.js (window.GUIDE_DATA), which
   build/build.py writes together with data.json. No network requests. */
(function (root) {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function num(v) {
    return v == null ? "" : String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }
  function range(a) {
    if (!a) { return "날짜 칸 없음"; }
    return a.start === a.end ? a.start + " 한 달" : a.start + "부터 " + a.end + "까지";
  }
  function byId(D, id) {
    for (var i = 0; i < D.datasets.length; i++) { if (D.datasets[i].id === id) { return D.datasets[i]; } }
    return null;
  }
  function statusText(d) {
    if (d.status === "newer") { return "설명보다 " + d.period.gap_months + "개월 최신"; }
    if (d.status === "match") { return "설명과 일치"; }
    if (d.status === "other_desc") { return "다른 데이터 설명"; }
    if (d.status === "changed") { return "설명이 바뀜"; }
    return "설명에 기간 없음";
  }
  function statusKey(d) { return d.status; }
  var STATUS_LABEL = {
    newer: "설명보다 최신", match: "설명과 일치", no_period: "설명에 기간 없음",
    other_desc: "다른 데이터 설명", changed: "설명이 바뀜", overdue: "등록 예정일 지남"
  };
  function tags(d) {
    var h = '<span class="tag ' + (d.status === "newer" ? "newer" : (d.status === "other_desc" || d.status === "changed" ? "flag" : "")) + '">' + esc(statusText(d)) + "</span>";
    if (d.status === "match" && d.period && d.period.gap_months != null && d.period.gap_months < 0) {
      h += '<span class="sub">실제 끝이 설명상 끝보다 ' + num(-d.period.gap_months) + "개월 이름</span>";
    }
    if (d.overdue_days) { h += '<br><span class="tag">차기 등록 예정일 ' + esc(d.next_date) + " 지남</span>"; }
    return h;
  }
  function basisText(a) {
    return a ? a.basis + " 기준" : "";
  }
  /* keep a "2025년 12월" date together on narrow screens */
  function dateHtml(s) {
    return esc(s).replace(/(\d{4}년 \d{1,2}월[가-힣]{0,4})/g, '<span class="nw">$1</span>');
  }
  /* long names such as 비정형데이터_생태갤러리 may wrap after the underscore */
  function nameHtml(s) { return esc(s).replace(/_/g, "_<wbr>"); }
  function statedText(d) {
    if (d.status === "other_desc") { return "다른 데이터의 설명임"; }
    if (d.period && d.period.stated_label) { return d.period.stated_label; }
    return "기간 없음";
  }

  /* ------------------------------------------------------------ first screen */
  function leadHtml(D) {
    var h = D.headline;
    var c = D.lead_case;
    var out = "한국체육산업개발 공공데이터를 내려받아 쓰는 개발자, 학생, 연구자를 위한 안내로, 데이터마다 실제 자료 기간, 이용 시 주의점, 권장 조건을 보여 줌. 공개 파일 <strong>" + num(h.datasets) +
      "종</strong> 가운데 설명에 기간이 적힌 <strong>" + num(h.period_stated) + "건 중 " + num(h.newer) +
      "건</strong>은 실제 자료가 설명보다 <strong>" + num(h.gap_min) + "개월에서 " + num(h.gap_max) + "개월 더 최신</strong>임.";
    if (c) {
      out += ' 예를 들어 <a href="dataset.html?id=' + esc(c.id) + '">' + esc(c.name) + "</a>에서 포털 설명의 '종료일이 9999-12-31'을 '" + esc(c.end_col) +
        "' 칸에 적용해 운영 중인 강좌를 거르면 <strong>" + num(c.in_end) + "행</strong>이 나옴. 9999-12-31 표시 " + num(c.in_start) + "행은 '" + esc(c.start_col) +
        "' 칸에 <span class=\"nw\">있음(전체 " + num(c.n_rows) + "행).</span>";
    }
    return out;
  }
  function factsHtml(D) {
    var h = D.headline;
    var rows = [
      ["자료 기준일", esc(D.asof) + " (공공데이터포털 데이터 페이지를 읽은 날)"],
      ["다음 대조 예정일", D.next_check ? esc(D.next_check) : "정하지 않음"],
      ["대상 범위", "공공데이터포털 파일데이터 " + num(h.datasets) + "종. 오픈API는 인증키가 필요해 대조하지 않음"],
      ["파일을 내려받은 날", esc(D.files_downloaded.join(", "))],
      ["출처", '<a href="' + esc(D.source.portal_url) + '" rel="noopener">' + esc(D.source.portal) + "</a>, 제공기관 " + esc(D.source.provider)],
      ["상태별 건수", "설명보다 최신 " + num(h.newer) + ", 설명과 일치 " + num(h.match) + ", 다른 데이터의 설명 " + num(h.other_desc) +
        ", 설명에 기간 없음 " + num(h.no_period) + (h.changed ? ", 설명이 바뀜 " + num(h.changed) : "")],
      ["내려받기", num(h.datasets) + "종 합계 " + num(h.downloads_total) + "회, 설명보다 최신인 <span class=\"nw\">" + num(h.newer) + "종 " + num(h.downloads_newer) + "회(" + h.downloads_newer_pct + "%)</span>"],
      ["행 수 대조", "CSV " + num(h.csv_files) + "개 중 " + num(h.csv_rows_match) + "개가 포털 '전체 행'과 같음"],
      ["이용 시 주의점", num(h.datasets_with_caution) + "종에 " + num(h.caution_total) + "건"]
    ];
    return rows.map(function (r) { return "<dt>" + r[0] + "</dt><dd>" + r[1] + "</dd>"; }).join("");
  }
  function methodNoteHtml(D) {
    return "실제 자료 기간은 파일의 주 날짜 칸에서 가장 이른 달과 가장 늦은 달이며, " + D.rule.ok_year_min + "년 이전과 " + D.rule.ok_year_max +
      "년 뒤의 날짜는 기본값이나 오타로 보고 뺌. 설명상 기간은 포털 설명에 적힌 연월이고, 연도만 있으면 끝을 그해 12월로 봄. " +
      '자세한 규칙은 <a href="method.html">계산 방법과 출처</a>에 있음.';
  }
  function filterSort(D, st) {
    var q = (st.q || "").trim().toLowerCase();
    var list = D.datasets.filter(function (d) {
      if (st.group && d.group !== st.group) { return false; }
      if (st.status === "overdue") { if (!d.overdue_days) { return false; } }
      else if (st.status === "caution") { if (!d.caution_count) { return false; } }
      else if (st.status && statusKey(d) !== st.status) { return false; }
      if (q && (d.name + " " + d.id + " " + d.group).toLowerCase().indexOf(q) < 0) { return false; }
      return true;
    });
    var key = st.sort || "group";
    var f = {
      downloads: function (a, b) { return (b.downloads || 0) - (a.downloads || 0); },
      gap: function (a, b) {
        var x = b.period && b.period.gap_months != null ? b.period.gap_months : -999;
        var y = a.period && a.period.gap_months != null ? a.period.gap_months : -999;
        return x - y;
      },
      caution: function (a, b) { return b.caution_count - a.caution_count; },
      end: function (a, b) { return ((b.actual && b.actual.end) || "").localeCompare((a.actual && a.actual.end) || ""); },
      name: function (a, b) { return a.name.localeCompare(b.name, "ko"); }
    }[key];
    if (f) { list = list.slice().sort(f); }
    return list;
  }
  function tableHtml(D, st) {
    var list = filterSort(D, st);
    var h = '<table class="stack wide"><caption>공개 파일의 실제 자료 기간과 포털 설명상 기간. 이름을 누르면 데이터별 안내로 이동함.</caption><thead><tr>' +
      '<th scope="col">데이터 이름</th><th scope="col">실제 자료 기간</th><th scope="col">설명상 기간</th><th scope="col">상태</th>' +
      '<th scope="col">갱신 주기와 다음 등록 예정일</th><th scope="col" class="r">내려받기</th><th scope="col" class="r">주의점</th></tr></thead><tbody>';
    list.forEach(function (d) {
      h += '<tr><th scope="row"><a href="dataset.html?id=' + esc(d.id) + '">' + nameHtml(d.name) + '</a><span class="sub">' + esc(d.group) + "</span></th>" +
        '<td data-label="실제 자료 기간">' + esc(range(d.actual)) + (d.actual || d.n_rows != null ? '<span class="sub">' + esc(basisText(d.actual)) +
          (d.actual && d.n_rows != null ? ", " : "") + (d.n_rows != null ? num(d.n_rows) + "행" : "") + "</span>" : "") + "</td>" +
        '<td data-label="설명상 기간">' + dateHtml(statedText(d)) + "</td>" +
        '<td data-label="상태">' + tags(d) + "</td>" +
        '<td data-label="갱신">' + esc(d.cycle || "") + '<span class="sub">' + (d.next_date ? "다음 등록 " + esc(d.next_date) : "다음 등록 예정일 없음") + "</span></td>" +
        '<td class="r" data-label="내려받기">' + num(d.downloads) + "회</td>" +
        '<td class="r" data-label="주의점">' + (d.caution_count ? num(d.caution_count) + "건" : "없음") + "</td></tr>";
    });
    if (!list.length) { h += '<tr><td colspan="7">조건에 맞는 데이터가 없음</td></tr>'; }
    return { html: h + "</tbody></table>", count: list.length };
  }

  /* ------------------------------------------------------------ dataset card */
  function chartHtml(d) {
    if (!d.monthly || !d.monthly.length) { return ""; }
    var map = {}, max = 0;
    d.monthly.forEach(function (m) { map[m[0]] = m[1]; if (m[1] > max) { max = m[1]; } });
    var s = d.actual.start.split("-"), e = d.actual.end.split("-");
    var y = +s[0], mo = +s[1], months = [];
    while (y < +e[0] || (y === +e[0] && mo <= +e[1])) {
      months.push((y + "-" + (mo < 10 ? "0" : "") + mo));
      mo++; if (mo > 12) { mo = 1; y++; }
    }
    var bw = months.length <= 40 ? 14 : (months.length <= 90 ? 8 : 5);
    var H = 140, left = 46, top = 8, W = left + months.length * (bw + 1) + 44;
    var rep = d.repeat;
    var g = '<svg width="' + W + '" height="' + (H + 34) + '" viewBox="0 0 ' + W + " " + (H + 34) + '" role="img" aria-label="' +
      esc(d.name + " 월별 행 수. " + range(d.actual) + ", 가장 많은 달 " + num(max) + "행") + '">';
    g += '<line x1="' + left + '" y1="' + top + '" x2="' + (W - 8) + '" y2="' + top + '"/><line x1="' + left + '" y1="' + (top + H) + '" x2="' + (W - 8) + '" y2="' + (top + H) + '"/>';
    g += '<text x="' + (left - 6) + '" y="' + (top + 10) + '" text-anchor="end">' + num(max) + '</text><text x="' + (left - 6) + '" y="' + (top + H) + '" text-anchor="end">0</text>';
    months.forEach(function (m, i) {
      var v = map[m] || 0, bh = max ? Math.round(v / max * H) : 0, x = left + i * (bw + 1);
      if (v && bh < 1) { bh = 1; }
      var inRep = rep && m >= rep.start && m <= rep.end;
      if (bh) { g += '<rect class="bar' + (inRep ? " rep" : "") + '" x="' + x + '" y="' + (top + H - bh) + '" width="' + bw + '" height="' + bh + '"><title>' + m + " " + num(v) + "행</title></rect>"; }
      if (i === 0 || (m.slice(5) === "01" && i * (bw + 1) >= 56)) {
        g += '<text x="' + x + '" y="' + (top + H + 16) + '">' + (i === 0 ? m : m.slice(0, 4)) + "</text>";
      }
    });
    g += "</svg>";
    var h = '<div class="chart" role="region" tabindex="0" aria-label="월별 행 수 그래프, 옆으로 넘겨 볼 수 있음">' + g + "</div>";
    if (rep) { h += '<p class="legend"><i></i>같은 내용이 되풀이되는 구간 (' + esc(rep.start) + "부터 " + esc(rep.end) + "까지 " + num(rep.months) + "개월, 월 " + num(rep.rows_per_month) + "행)</p>"; }
    h += '<details><summary>월별 행 수를 표로 보기</summary><div class="scroll"><table><thead><tr><th scope="col">월</th><th scope="col" class="r">행 수</th></tr></thead><tbody>';
    months.forEach(function (m) { h += "<tr><td>" + m + '</td><td class="r">' + num(map[m] || 0) + "</td></tr>"; });
    return h + "</tbody></table></div></details>";
  }
  function columnsHtml(d) {
    if (!d.columns) { return ""; }
    var kind = { date: "날짜", number: "숫자", text: "글자" };
    var h = '<div class="scroll"><table class="stack"><caption>칸별 빈칸 비율과 값의 범위. 값 종류가 많은 글자 칸은 사람 이름이 들어 있을 수 있어 예시를 싣지 않음.</caption><thead><tr>' +
      '<th scope="col">칸 이름</th><th scope="col">종류</th><th scope="col" class="r">빈칸</th><th scope="col" class="r">서로 다른 값</th><th scope="col">값의 범위나 예</th></tr></thead><tbody>';
    d.columns.forEach(function (c) {
      var v;
      if (c.kind === "date") {
        v = (c.min ? esc(c.min) + "부터 " + esc(c.max) + "까지" : "범위 안 날짜 없음") + (c.odd_rows ? ", 범위 밖 날짜 " + num(c.odd_rows) + "행" : "");
      } else if (c.kind === "number") {
        v = esc(c.min) + "부터 " + esc(c.max) + "까지";
      } else if (c.examples) {
        v = c.examples.map(function (x) { return "'" + esc(x) + "'"; }).join(", ");
      } else { v = c.distinct ? "값 종류가 많아 예시 생략" : "값 없음"; }
      h += '<tr><th scope="row">' + esc(c.name) + '</th><td data-label="종류">' + kind[c.kind] + '</td><td class="r" data-label="빈칸">' + c.blank_pct + "% (" + num(c.blank) + '행)</td><td class="r" data-label="서로 다른 값">' + num(c.distinct) + '</td><td data-label="범위나 예">' + v + "</td></tr>";
    });
    return h + "</tbody></table></div>";
  }
  function notesHtml(d, level) {
    var list = d.notes.filter(function (n) { return n.level === level; });
    if (!list.length) { return ""; }
    if (level === "info") {
      return '<ul class="plain">' + list.map(function (n) { return "<li>" + esc(n.title) + ". " + esc(n.body) + "</li>"; }).join("") + "</ul>";
    }
    return '<ol class="notes">' + list.map(function (n) {
      return "<li><h3>" + esc(n.title) + "</h3><p>" + esc(n.body) + "</p>" + (n.use ? '<p class="use"><b>권장 조건</b>' + esc(n.use) + "</p>" : "") + "</li>";
    }).join("") + "</ol>";
  }
  function datasetHtml(D, id) {
    var d = byId(D, id);
    if (!d) {
      return { title: "데이터를 찾지 못함", html: '<h1>데이터를 찾지 못함</h1><p>주소의 번호에 맞는 데이터가 없음. <a href="index.html">전체 목록</a>에서 다시 고를 것.</p>' };
    }
    var p = d.period || {};
    var h = '<p class="crumb"><a href="index.html">전체 목록</a> 아래 ' + esc(d.group) + "</p><h1>" + esc(d.name) + "</h1>";
    h += '<p class="lead">' + tags(d).replace("<br>", " ") + "</p>";
    h += '<dl class="facts"><dt>자료 기준일</dt><dd>' + esc(D.asof) + "</dd><dt>파일을 내려받은 날</dt><dd>" + esc(d.file.downloaded || "") +
      '</dd><dt>원래 페이지</dt><dd><a href="' + esc(d.url) + '" rel="noopener">공공데이터포털에서 이 데이터 열기</a></dd></dl>';

    h += "<h2>포털 설명과 실제 파일</h2>";
    h += '<div class="scroll"><table class="compare"><thead><tr><th scope="col">항목</th><th scope="col">포털 설명</th><th scope="col">실제 파일</th></tr></thead><tbody>';
    h += '<tr><th scope="row">자료 기간</th><td>' + dateHtml(statedText(d)) + "</td><td>" + esc(range(d.actual)) +
      (d.actual ? '<span class="sub">' + esc(basisText(d.actual)) + (d.actual.excluded_rows ? ", 범위 밖 날짜 " + num(d.actual.excluded_rows) + "행 제외" : "") +
        (d.actual.unread_rows ? ", 빈칸이거나 날짜로 읽지 못한 " + num(d.actual.unread_rows) + "행 제외" : "") + "</span>" : "") + "</td></tr>";
    if (d.n_rows != null) {
      h += '<tr><th scope="row">행 수</th><td>전체 행 ' + num(d.rows) + "</td><td>" + num(d.n_rows) + "행" + '<span class="sub">' + (d.rows_match ? "포털과 같음" : "포털과 다름") + "</span></td></tr>";
    } else if (d.zip) {
      h += '<tr><th scope="row">건수</th><td>' + (d.zip.desc_count ? "설명에 " + num(d.zip.desc_count) + "건" : "설명에 건수 없음") + "</td><td>압축 파일 안 파일 " + num(d.zip.entries) + "개, 사진 " + num(d.zip.images) + "장</td></tr>";
    }
    h += '<tr><th scope="row">날짜 표시</th><td>수정일 ' + esc(d.modified) + ", 등록일 " + esc(d.created) + "</td><td>" + (d.actual ? "파일 안 최신 월 " + esc(d.actual.end) : "날짜 칸 없음") + "</td></tr>";
    h += "</tbody></table></div>";
    if (p.sentence) {
      h += "<h3>기간을 적은 설명 문장</h3><blockquote>" + esc(p.sentence) + "<footer>공공데이터포털 설명, " + esc(D.asof) + " 확인" +
        (p.same_as_name ? ". 이 설명 전체가 '" + esc(p.same_as_name) + "' 데이터의 설명과 같음" : "") + "</footer></blockquote>";
    }
    if (d.status === "newer") {
      h += "<p>설명상 끝 시점(" + esc(p.stated_end) + ")보다 파일의 가장 늦은 달(" + esc(d.actual.end) + ")이 " + num(p.gap_months) + "개월 뒤임." +
        (p.start_differs ? " 시작 시점도 설명과 다름." : "") + ' 고칠 문안은 <a href="suggestions.html#s-' + esc(d.id) + '">설명 갱신 제안</a>에 있음.</p>';
    }

    var cautions = notesHtml(d, "caution");
    h += "<h2>이용 시 주의점</h2>" + (cautions || "<p>파일에서 계산한 주의점이 없음.</p>");
    var info = notesHtml(d, "info");
    if (info) { h += "<h3>참고</h3>" + info; }
    if (d.caveat) { h += "<h3>포털에 적힌 기타 유의사항</h3><blockquote>" + esc(d.caveat) + "<footer>공공데이터포털, " + esc(D.asof) + " 확인</footer></blockquote>"; }

    if (d.monthly && d.monthly.length) { h += "<h2>월별 행 수</h2><p class=\"note-line\">" + esc(d.actual.basis) + " 기준으로 달마다 행을 센 값임.</p>" + chartHtml(d); }
    if (d.columns) { h += "<h2>칸별 빈칸 비율과 값</h2>" + columnsHtml(d); }

    h += '<h2>파일 정보</h2><dl class="facts">' +
      "<dt>파일데이터명</dt><dd>" + esc(d.file_title) + "</dd>" +
      "<dt>내려받은 파일 이름</dt><dd>" + esc(d.file.filename || "") + " (" + num(d.file.bytes) + "바이트)</dd>" +
      "<dt>글자 부호</dt><dd>" + esc(d.encoding === "zip" ? "압축 파일" : d.encoding) + "</dd>" +
      "<dt>업데이트 주기</dt><dd>" + esc(d.cycle || "") + "</dd>" +
      "<dt>차기 등록 예정일</dt><dd>" + esc(d.next_date || "없음") + "</dd>" +
      "<dt>관리 부서</dt><dd>" + esc(d.dept || "") + "</dd>" +
      "<dt>이용허락범위</dt><dd>" + esc(d.license || "") + "</dd>" +
      "<dt>내려받기 수</dt><dd>" + num(d.downloads) + "회</dd></dl>";
    h += "<h2>포털 설명 전문</h2><blockquote>" + esc(d.desc) + "<footer>공공데이터포털, " + esc(D.asof) + " 확인</footer></blockquote>";
    return { title: d.name, html: h };
  }

  /* ------------------------------------------------------------ suggestions */
  function suggestionsHtml(D) {
    var h = "", seen = {};
    D.suggestions.forEach(function (s, i) {
      var anchor = seen[s.id] ? "" : ' id="s-' + esc(s.id) + '"';
      seen[s.id] = true;
      h += '<section class="sugg"' + anchor + "><h3>" + esc(s.name) + ' <span class="tag">' + esc(s.type) + "</span></h3><dl>" +
        "<dt>내려받기</dt><dd>" + num(s.downloads) + '회, <a href="dataset.html?id=' + esc(s.id) + '">데이터별 안내 보기</a></dd>' +
        "<dt>지금 설명</dt><dd>" + esc(s.current) + "</dd>" +
        '<dt>제안 문장</dt><dd><div class="proposed" id="p-' + i + '">' + esc(s.proposed) + '</div><div class="copyrow"><button type="button" data-copy="p-' + i + '">제안 문장 복사</button><span class="done" role="status" aria-live="polite"></span></div></dd>' +
        "<dt>근거</dt><dd>" + esc(s.evidence) + "</dd></dl></section>";
    });
    return h;
  }
  function scheduleHtml(D) {
    if (!D.schedule.length) { return "<p>기준일부터 60일 안에 등록 예정일이 있는 데이터가 없음.</p>"; }
    var h = '<div class="scroll"><table class="stack"><caption>기준일 ' + esc(D.asof) + '부터 60일 안에 차기 등록 예정일이 있거나 이미 지난 데이터</caption><thead><tr><th scope="col">데이터 이름</th><th scope="col">업데이트 주기</th><th scope="col">차기 등록 예정일</th><th scope="col">기준일과의 차이</th><th scope="col">파일 안 최신 월</th></tr></thead><tbody>';
    D.schedule.forEach(function (s) {
      h += '<tr><th scope="row"><a href="dataset.html?id=' + esc(s.id) + '">' + nameHtml(s.name) + '</a></th><td data-label="주기">' + esc(s.cycle) + '</td><td data-label="예정일">' + esc(s.next_date) +
        '</td><td data-label="차이">' + (s.days < 0 ? num(-s.days) + "일 지남" : num(s.days) + "일 남음") + '</td><td data-label="최신 월">' + esc(s.actual_end || "날짜 칸 없음") + "</td></tr>";
    });
    return h + "</tbody></table></div>";
  }
  function changesHtml(D) {
    var c = D.changes;
    if (!c) { return "<p>앞선 대조 기록이 없어 비교하지 않음.</p>"; }
    var h = "<p>" + esc(c.prev) + "에 읽은 포털 쪽과 " + esc(D.asof) + "에 읽은 포털 쪽을 비교함. " + num(D.headline.datasets) + "종의 설명, 파일데이터명, 전체 행, 수정일, 차기 등록 예정일, 업데이트 주기 가운데 바뀐 항목은 " + num(c.items.length) + "건임. 같은 기간 내려받기는 " + num(c.downloads_added) + "회 늘어 합계 " + num(D.headline.downloads_total) + "회임.</p>";
    if (c.items.length) {
      h += '<div class="scroll"><table class="stack"><thead><tr><th scope="col">데이터 이름</th><th scope="col">항목</th><th scope="col">이전</th><th scope="col">지금</th></tr></thead><tbody>';
      c.items.forEach(function (x) {
        h += '<tr><th scope="row">' + esc(x.name) + '</th><td data-label="항목">' + esc(x.field) + '</td><td data-label="이전">' + esc(x.before) + '</td><td data-label="지금">' + esc(x.after) + "</td></tr>";
      });
      h += "</tbody></table></div><p class=\"note-line\">설명이 바뀐 데이터는 규칙표를 다시 확인한 뒤 반영 여부를 표시함.</p>";
    }
    return h;
  }

  /* ------------------------------------------------------------ method */
  function methodHtml(D) {
    var h = D.headline, r = D.rule;
    var titled = D.datasets.filter(function (d) { return d.title_month; }).map(function (d) { return esc(d.name); });
    var out = "<h2>계산 규칙</h2><ol class=\"notes\">" +
      "<li><h3>기간 표현 고르기</h3><p>공개 파일 " + num(h.datasets) + "종의 포털 설명에서 자기 자료의 기간을 적은 표현을 손으로 확인해 규칙표로 고정함. 기간 표현은 " + num(h.period_stated) + "건이고, 다른 데이터의 설명이 붙은 " + num(h.other_desc) + "건은 따로 셈.</p></li>" +
      "<li><h3>설명상 기간</h3><p>적힌 연월을 그대로 씀. 연도만 있으면 시작은 그해 1월, 끝은 그해 12월로 봄.</p></li>" +
      "<li><h3>실제 자료 기간</h3><p>파일의 주 날짜 칸에서 가장 이른 달과 가장 늦은 달임. " + r.ok_year_min + "년 이전과 " + r.ok_year_max + "년 뒤의 날짜는 기본값이나 오타로 보고 뺌." +
        (titled.length ? " 다만 " + titled.join(", ") + "처럼 제목에 'YYYY년 M월'로 자료의 달이 적힌 파일은 등록일 대신 제목의 연월을 씀." : "") + "</p></li>" +
      "<li><h3>판정</h3><p>실제 끝 시점이 설명상 끝 시점보다 늦으면 '설명보다 최신', 같거나 이르면 '설명과 일치'로 봄. 설명에 끝 시점이 '현재'로 적힌 경우도 일치로 봄.</p></li>" +
      "<li><h3>설명이 바뀐 경우</h3><p>규칙표의 표현이 포털 설명에서 사라지면 그 데이터를 '설명이 바뀜'으로 표시하고 규칙표를 다시 확인함. 지금은 " + num(h.changed) + "건임.</p></li></ol>";

    out += "<h2>기간 표현 규칙표</h2>";
    out += '<div class="scroll"><table class="stack wide"><caption>포털 설명 ' + esc(D.asof) + " 확인, 파일 계산값과 나란히 놓음</caption><thead><tr><th scope=\"col\">데이터 이름</th><th scope=\"col\">설명 문장</th><th scope=\"col\">설명상 기간</th><th scope=\"col\">실제 자료 기간</th><th scope=\"col\">판정</th><th scope=\"col\" class=\"r\">내려받기</th></tr></thead><tbody>";
    D.datasets.filter(function (d) { return d.period; }).sort(function (a, b) {
      return ((b.period.gap_months == null ? -99 : b.period.gap_months) - (a.period.gap_months == null ? -99 : a.period.gap_months));
    }).forEach(function (d) {
      out += '<tr><th scope="row"><a href="dataset.html?id=' + esc(d.id) + '">' + nameHtml(d.name) + '</a><span class="sub">' + esc(d.id) + '</span></th><td data-label="설명 문장">' + esc(d.period.sentence || "") +
        '</td><td data-label="설명상 기간">' + dateHtml(statedText(d)) + '</td><td data-label="실제 기간">' + esc(range(d.actual)) + '<span class="sub">' + esc(basisText(d.actual)) + "</span>" +
        '</td><td data-label="판정">' + tags(d) + '</td><td class="r" data-label="내려받기">' + num(d.downloads) + "회</td></tr>";
    });
    out += "</tbody></table></div>";

    out += "<h2>기간 표현으로 보지 않은 문장</h2><p>설명에 연도가 들어 있지만 자료 기간을 적은 것이 아니어서 대조에서 뺀 문장임.</p>";
    out += '<div class="scroll"><table class="stack drop"><thead><tr><th scope="col">데이터 이름</th><th scope="col">문장</th><th scope="col">뺀 이유</th></tr></thead><tbody>';
    D.not_period.forEach(function (x) {
      out += '<tr><th scope="row">' + esc(x.name) + '</th><td data-label="문장">' + esc(x.sentence) + '</td><td data-label="이유">' + esc(x.reason) + "</td></tr>";
    });
    out += "</tbody></table></div>";

    var lic = Object.keys(h.licenses).map(function (k) { return esc(k) + " " + num(h.licenses[k]) + "종"; }).join(", ");
    var special = D.datasets.filter(function (d) { return d.license !== "이용허락범위 제한 없음"; }).map(function (d) { return esc(d.name); }).join(", ");
    var months = Object.keys(h.modified_months).map(function (k) { return k + "에 " + num(h.modified_months[k]) + "종"; }).join(", ");
    out += "<h2>범위와 한계</h2><ul class=\"plain\">" +
      "<li>대상은 한국체육산업개발이 공공데이터포털에 올린 파일데이터 " + num(h.datasets) + "종임. 오픈API는 인증키가 필요해 대조하지 않음.</li>" +
      "<li>포털 쪽은 " + esc(D.asof) + "에 읽었고, 파일은 " + esc(D.files_downloaded.join(", ")) + "에 내려받음. 그 사이 파일이 바뀌었는지는 포털 '전체 행'과 파일 행 수의 대조로 확인하며, CSV " + num(h.csv_files) + "개 중 " + num(h.csv_rows_match) + "개가 같음.</li>" +
      "<li>포털의 수정일은 " + esc(h.modified_min) + "부터 " + esc(h.modified_max) + "까지이고 " + months + "임. 수정일만으로는 자료가 어느 달까지 들어 있는지 알 수 없어 파일 안 최신 월을 따로 보여 줌.</li>" +
      "<li>주의점은 파일에서 센 값임. 값의 뜻은 담당 부서 확인이 필요한 것이 있으며, 그런 항목은 '보임', '확인'으로 적음.</li>" +
      "<li>값 종류가 많은 글자 칸의 값과 표본 행은 싣지 않음. 강좌명 같은 칸에 사람 이름이 들어 있을 수 있기 때문임.</li>" +
      "<li>글자 부호는 " + Object.keys(h.encodings).map(function (k) { return esc(k === "zip" ? "압축 파일" : k) + " " + num(h.encodings[k]) + "개"; }).join(", ") + "임.</li></ul>";

    out += "<h2>출처와 이용허락범위</h2><ul class=\"plain\">" +
      '<li>자료 출처는 <a href="' + esc(D.source.portal_url) + '" rel="noopener">' + esc(D.source.portal) + "</a>의 " + esc(D.source.provider) + " 파일데이터임.</li>" +
      "<li>포털에 적힌 이용허락범위는 " + lic + "임." + (special ? " 제한이 적힌 데이터는 <span class=\"nw\">" + special + "임.</span>" : "") + " 이 안내는 설명 인용과 계산값만 싣고 파일 자체는 싣지 않음.</li>" +
      '<li>올림픽수영장 요일 칸의 토요일 표시 설명은 한국체육산업개발 누리집 <a href="' + esc(D.source.pool_fee.url) + '" rel="noopener">올림픽수영장 요금 안내</a>를 ' + esc(D.source.pool_fee.checked) + "에 확인한 것임.</li>" +
      '<li>화면의 모든 숫자는 <a href="data.json">data.json</a>에서 읽음.</li></ul>';
    return out;
  }

  var Guide = {
    leadHtml: leadHtml, factsHtml: factsHtml, methodNoteHtml: methodNoteHtml, tableHtml: tableHtml, filterSort: filterSort,
    datasetHtml: datasetHtml, suggestionsHtml: suggestionsHtml, scheduleHtml: scheduleHtml, changesHtml: changesHtml,
    methodHtml: methodHtml, STATUS_LABEL: STATUS_LABEL
  };

  /* ------------------------------------------------------------ page wiring */
  function $(id) { return document.getElementById(id); }
  /* keep dates such as 2007-04 or 2026-08-11 and quoted ranges such as '시작일~종료일' on one line
     (browsers may wrap after the hyphen or tilde). Text nodes only, so copied text is unchanged. */
  var KEEP_RE = /(?:[가-힣]{1,8}\( ?)?\d{4}-\d{2}(?:-\d{2})?[가-힣]{0,6}[,.)]?|'[^'\s]{1,24}'[가-힣]{0,3}/g;
  function keepTokens(el) {
    if (!el || !document.createTreeWalker) { return; }
    var w = document.createTreeWalker(el, 4, null), nodes = [], n;
    while ((n = w.nextNode())) {
      if (n.parentNode && n.parentNode.className !== "nw" && /\d{4}-\d{2}|'[^'\s]{1,24}'/.test(n.nodeValue)) { nodes.push(n); }
    }
    nodes.forEach(function (t) {
      var s = t.nodeValue, last = 0, m, frag = document.createDocumentFragment();
      KEEP_RE.lastIndex = 0;
      while ((m = KEEP_RE.exec(s))) {
        if (m.index > last) { frag.appendChild(document.createTextNode(s.slice(last, m.index))); }
        var sp = document.createElement("span"); sp.className = "nw"; sp.textContent = m[0]; frag.appendChild(sp);
        last = m.index + m[0].length;
      }
      if (!last) { return; }
      if (last < s.length) { frag.appendChild(document.createTextNode(s.slice(last))); }
      t.parentNode.replaceChild(frag, t);
    });
  }
  function footer(D) {
    var f = $("foot-data");
    if (f) { f.textContent = "자료 기준일 " + D.asof + ". 출처 " + D.source.portal + ", 제공기관 " + D.source.provider + "."; }
  }
  function bootIndex(D) {
    $("lead").innerHTML = leadHtml(D);
    $("facts").innerHTML = factsHtml(D);
    $("method-note").innerHTML = methodNoteHtml(D);
    var gs = $("f-group"), ss = $("f-status");
    D.groups.forEach(function (g) { var o = document.createElement("option"); o.value = g; o.textContent = g; gs.appendChild(o); });
    ["newer", "match", "other_desc", "no_period", "changed", "overdue"].forEach(function (k) {
      var n = D.datasets.filter(function (d) { return k === "overdue" ? d.overdue_days : d.status === k; }).length;
      if (!n) { return; }
      var o = document.createElement("option"); o.value = k; o.textContent = STATUS_LABEL[k] + " " + n + "종"; ss.appendChild(o);
    });
    var oc = document.createElement("option"); oc.value = "caution"; oc.textContent = "주의점 있음 " + D.headline.datasets_with_caution + "종"; ss.appendChild(oc);
    function draw() {
      var t = tableHtml(D, { q: $("f-q").value, group: gs.value, status: ss.value, sort: $("f-sort").value });
      $("table").innerHTML = t.html;
      keepTokens($("table"));
      $("count").textContent = D.datasets.length + "종 중 " + t.count + "종 표시";
    }
    ["f-q", "f-group", "f-status", "f-sort"].forEach(function (id) { $(id).addEventListener("input", draw); $(id).addEventListener("change", draw); });
    $("filters").addEventListener("submit", function (ev) { ev.preventDefault(); });
    draw();
  }
  function bootDataset(D) {
    var m = /[?&]id=(\d+)/.exec(location.search);
    var r = datasetHtml(D, m ? m[1] : "");
    $("app").innerHTML = r.html;
    document.title = r.title + " | 한국체육산업개발 공공데이터 이용 안내";
  }
  function copyText(text, done) {
    function ok() { done.textContent = "복사함"; setTimeout(function () { done.textContent = ""; }, 2500); }
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.top = "-1000px";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); ok(); } catch (e) { done.textContent = "복사하지 못함. 문장을 직접 골라 복사할 것"; }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(text).then(ok, fallback); } else { fallback(); }
  }
  function bootSuggestions(D) {
    var paste = D.suggestions.filter(function (s) { return s.type === "설명 문장 갱신" || s.type === "설명 전체 교체"; }).length;
    $("intro").textContent = "담당 부서용 제안 " + D.suggestions.length + "건으로, 포털 설명을 고칠 때 붙여 쓸 수 있는 문안 " + paste + "건과 근거를 붙인 확인 요청 " + (D.suggestions.length - paste) + "건임. 내려받기 수가 많은 데이터부터 놓았고, 근거 숫자는 모두 내려받은 파일에서 센 값임.";
    $("sugg").innerHTML = suggestionsHtml(D);
    $("schedule").innerHTML = scheduleHtml(D);
    $("changes").innerHTML = changesHtml(D);
    $("sugg").addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("button[data-copy]") : null;
      if (!b) { return; }
      copyText($(b.getAttribute("data-copy")).textContent, b.parentNode.querySelector(".done"));
    });
    if (location.hash && $(location.hash.slice(1))) { $(location.hash.slice(1)).scrollIntoView(); }
  }
  function boot() {
    var D = root.GUIDE_DATA, page = document.body.getAttribute("data-page");
    if (!D) { $("app-error").hidden = false; return; }
    footer(D);
    if (page === "index") { bootIndex(D); }
    else if (page === "dataset") { bootDataset(D); }
    else if (page === "suggestions") { bootSuggestions(D); }
    else if (page === "method") { $("app").innerHTML = methodHtml(D); }
    keepTokens($("main"));
  }

  if (typeof module !== "undefined" && module.exports) { module.exports = Guide; }
  else if (root.document) {
    if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", boot); } else { boot(); }
  }
})(typeof window !== "undefined" ? window : this);
