// People and year suggestions for the quick-search dropdowns (homepage box
// and the ⌘K search window on every page), like the storyline search.
//  - Type a name ("contini"): the matching people are listed first, each with
//    how many records the dataset holds on them, per section. Clicking a
//    person opens their results on search.html.
//  - Type a year ("1950"): that year is listed with its records per section,
//    then the people who appear in that year's records, most present first.
//    Clicking the year opens all its records; clicking a person opens theirs.
//
// Used by each page's renderResults():
//   window.ogPeopleSuggest(q, ALL_DATA) || window.ogYearSuggest(q, ALL_DATA)
// each returns a ready-made block of elements, or null when nothing matches.
// search.html also shows them above its results with {inPage: true}: no
// "Schede" heading, no row for the exact person/year already being shown.
(function () {
  var CATS = [
    ['letter', 'Ep.', '#5a1e7a', 'Epistolario'],
    ['library', 'Bib.', '#7a3b1e', 'Biblioteca'],
    ['primary bibliography', 'Bib. prim.', '#1a6a40', 'Bib. primaria'],
    ['secondary bibliography', 'Bib. sec.', '#1e4a7a', 'Bib. secondaria'],
    ['archive', 'Arc.', '#6a3a1a', 'Archivi'],
    ['translation', 'Trad.', '#6a5a1a', 'Traduzioni']
  ];
  var MAX_PEOPLE = 4;        // people matching a typed name
  var MAX_YEAR_PEOPLE = 5;   // people listed under a typed year
  var GADDA = 'gadda carlo emilio'; // left out of the year lists: he is in almost everything

  var css = document.createElement('style');
  css.textContent =
    '.ps-head { padding: 0.45rem 1rem 0.2rem; font-family: "DM Mono", monospace; font-size: 9px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted, #7a7268); }' +
    '.ps-person { display: flex; align-items: center; gap: 10px; padding: 0.55rem 1rem; border-bottom: 1px solid var(--border, #c8bfaa); text-decoration: none; color: var(--ink, #1a1814); }' +
    '.ps-person:hover { background: var(--paper, #f5f0e8); }' +
    '.ps-person:hover .ps-name { color: var(--accent, #7a3b1e); }' +
    '.ps-name { flex: 1 1 auto; min-width: 0; font-size: 1rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }' +
    '.ps-year .ps-name { font-family: "DM Mono", monospace; font-size: 1.05rem; }' +
    '.ps-counts { flex: 0 0 auto; display: flex; gap: 4px; flex-wrap: wrap; justify-content: flex-end; }' +
    '.ps-count { font-family: "DM Mono", monospace; font-size: 9px; padding: 1px 6px; border-radius: 2px; white-space: nowrap; }' +
    '.ps-total { font-family: "DM Mono", monospace; font-size: 10px; color: var(--muted, #7a7268); flex: 0 0 auto; min-width: 4.5em; text-align: right; }';
  document.head.appendChild(css);

  // Names that differ only by a comma or accents are the same person
  // ("Contini Gianfranco" in the letters, "Contini, Gianfranco" elsewhere).
  function key(s) {
    return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/,/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
  }
  // The search link for a person: the name without commas finds both spellings.
  function personHref(label) { return 'search.html?q=' + encodeURIComponent(label.replace(/,/g, '')); }

  // People, with their records per section: overall, and per year.
  var cache = { data: null };
  function index(data) {
    if (cache.data === data) return cache;
    var byKey = {}, byYear = {};
    data.forEach(function (d) {
      var y = d.year;
      if (y && !byYear[y]) byYear[y] = { total: 0, cats: {}, people: {} };
      if (y) { byYear[y].total++; byYear[y].cats[d.category] = (byYear[y].cats[d.category] || 0) + 1; }
      var seen = {};
      (d.people || []).forEach(function (p) {
        if (!p.name) return;
        var k = key(p.name);
        var e = byKey[k] || (byKey[k] = { key: k, label: p.name, total: 0, cats: {} });
        if (p.name.indexOf(',') !== -1) e.label = p.name; // show the "Surname, Name" form
        if (seen[k]) return; // a person named twice in one record counts once
        seen[k] = true;
        e.total++;
        e.cats[d.category] = (e.cats[d.category] || 0) + 1;
        if (y && k.indexOf(GADDA) !== 0) {
          var yp = byYear[y].people[k] || (byYear[y].people[k] = { key: k, total: 0, cats: {} });
          yp.total++;
          yp.cats[d.category] = (yp.cats[d.category] || 0) + 1;
        }
      });
    });
    cache = { data: data, people: Object.values(byKey), byKey: byKey, byYear: byYear };
    return cache;
  }

  function head(text) {
    var h = document.createElement('div');
    h.className = 'ps-head';
    h.textContent = text;
    return h;
  }
  // One row: a name (or year), its records per section, and the total.
  function row(label, cats, total, href, title, extraClass, totalText) {
    var a = document.createElement('a');
    a.className = 'ps-person' + (extraClass ? ' ' + extraClass : '');
    a.href = href;
    a.title = title;
    var name = document.createElement('span');
    name.className = 'ps-name';
    name.textContent = label;
    var counts = document.createElement('span');
    counts.className = 'ps-counts';
    CATS.forEach(function (c) {
      var n = cats[c[0]];
      if (!n) return;
      var b = document.createElement('span');
      b.className = 'ps-count';
      b.style.cssText = 'background:' + c[2] + '18;color:' + c[2] + ';border:1px solid ' + c[2] + '40';
      b.textContent = c[1] + ' ' + n;
      b.title = c[3] + ': ' + n;
      counts.appendChild(b);
    });
    var tot = document.createElement('span');
    tot.className = 'ps-total';
    tot.textContent = totalText || (total + (total === 1 ? ' scheda' : ' schede'));
    a.appendChild(name);
    a.appendChild(counts);
    a.appendChild(tot);
    return a;
  }

  window.ogPeopleSuggest = function (q, data, opts) {
    var inPage = opts && opts.inPage;
    var qk = key(q);
    if (!data || !data.length || qk.length < 3 || /^\d{4}$/.test(qk)) return null;
    var tokens = qk.split(' ');
    var hits = index(data).people
      .filter(function (e) { return !(inPage && e.key === qk) && tokens.every(function (t) { return e.key.indexOf(t) !== -1; }); })
      .sort(function (a, b) { return b.total - a.total; })
      .slice(0, MAX_PEOPLE);
    if (!hits.length) return null;
    var frag = document.createDocumentFragment();
    frag.appendChild(head('Persone'));
    hits.forEach(function (e) {
      frag.appendChild(row(e.label, e.cats, e.total, personHref(e.label), 'Tutte le schede di ' + e.label));
    });
    if (!inPage) frag.appendChild(head('Schede'));
    return frag;
  };

  window.ogYearSuggest = function (q, data, opts) {
    var inPage = opts && opts.inPage;
    var qk = key(q);
    if (!data || !data.length || !/^\d{4}$/.test(qk)) return null;
    var ix = index(data);
    var y = ix.byYear[+qk];
    if (!y) return null;
    var people = Object.values(y.people)
      .sort(function (a, b) { return b.total - a.total || a.key.localeCompare(b.key); })
      .slice(0, MAX_YEAR_PEOPLE);
    var frag = document.createDocumentFragment();
    if (!inPage) {
      frag.appendChild(head('Anno'));
      frag.appendChild(row(qk, y.cats, y.total, 'search.html?q=' + qk, 'Tutte le schede del ' + qk, 'ps-year'));
    }
    if (people.length) {
      frag.appendChild(head('Persone nel ' + qk));
      people.forEach(function (p) {
        var label = ix.byKey[p.key].label;
        frag.appendChild(row(label, p.cats, p.total, personHref(label), 'Tutte le schede di ' + label, '', p.total + ' nel ' + qk));
      });
    }
    if (!frag.childNodes.length) return null;
    if (!inPage) frag.appendChild(head('Schede'));
    return frag;
  };
})();
