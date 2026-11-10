// People suggestions for the quick-search dropdowns (homepage box and the
// ⌘K search window on every page). As you type a name, matching people are
// listed first — like the storyline search — each with how many records the
// dataset holds on them, per section. Clicking a person opens their results
// on search.html.
//
// Used by each page's renderResults(): window.ogPeopleSuggest(q, ALL_DATA)
// returns a ready-made block of elements, or null when nobody matches.
(function () {
  var CATS = [
    ['letter', 'Ep.', '#5a1e7a', 'Epistolario'],
    ['library', 'Bib.', '#7a3b1e', 'Biblioteca'],
    ['primary bibliography', 'Bib. prim.', '#1a6a40', 'Bib. primaria'],
    ['secondary bibliography', 'Bib. sec.', '#1e4a7a', 'Bib. secondaria'],
    ['archive', 'Arc.', '#6a3a1a', 'Archivi'],
    ['translation', 'Trad.', '#6a5a1a', 'Traduzioni']
  ];
  var MAX_PEOPLE = 4;

  var css = document.createElement('style');
  css.textContent =
    '.ps-head { padding: 0.45rem 1rem 0.2rem; font-family: "DM Mono", monospace; font-size: 9px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted, #7a7268); }' +
    '.ps-person { display: flex; align-items: center; gap: 10px; padding: 0.55rem 1rem; border-bottom: 1px solid var(--border, #c8bfaa); text-decoration: none; color: var(--ink, #1a1814); }' +
    '.ps-person:hover { background: var(--paper, #f5f0e8); }' +
    '.ps-person:hover .ps-name { color: var(--accent, #7a3b1e); }' +
    '.ps-name { flex: 1 1 auto; min-width: 0; font-size: 1rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }' +
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

  var cache = { data: null, people: null };
  function peopleOf(data) {
    if (cache.data === data) return cache.people;
    var byKey = {};
    data.forEach(function (d) {
      (d.people || []).forEach(function (p) {
        if (!p.name) return;
        var k = key(p.name);
        var e = byKey[k] || (byKey[k] = { key: k, label: p.name, total: 0, cats: {} });
        if (p.name.indexOf(',') !== -1) e.label = p.name; // show the "Surname, Name" form
        e.total++;
        e.cats[d.category] = (e.cats[d.category] || 0) + 1;
      });
    });
    cache = { data: data, people: Object.values(byKey) };
    return cache.people;
  }

  window.ogPeopleSuggest = function (q, data) {
    var qk = key(q);
    if (!data || !data.length || qk.length < 3 || /^\d{4}$/.test(qk)) return null;
    var tokens = qk.split(' ');
    var hits = peopleOf(data)
      .filter(function (e) { return tokens.every(function (t) { return e.key.indexOf(t) !== -1; }); })
      .sort(function (a, b) { return b.total - a.total; })
      .slice(0, MAX_PEOPLE);
    if (!hits.length) return null;

    var frag = document.createDocumentFragment();
    var head = document.createElement('div');
    head.className = 'ps-head';
    head.textContent = 'Persone';
    frag.appendChild(head);
    hits.forEach(function (e) {
      var a = document.createElement('a');
      a.className = 'ps-person';
      a.href = 'search.html?q=' + encodeURIComponent(e.label.replace(/,/g, ''));
      a.title = 'Tutte le schede di ' + e.label;
      var name = document.createElement('span');
      name.className = 'ps-name';
      name.textContent = e.label;
      var counts = document.createElement('span');
      counts.className = 'ps-counts';
      CATS.forEach(function (c) {
        var n = e.cats[c[0]];
        if (!n) return;
        var b = document.createElement('span');
        b.className = 'ps-count';
        b.style.cssText = 'background:' + c[2] + '18;color:' + c[2] + ';border:1px solid ' + c[2] + '40';
        b.textContent = c[1] + ' ' + n;
        b.title = c[3] + ': ' + n;
        counts.appendChild(b);
      });
      var total = document.createElement('span');
      total.className = 'ps-total';
      total.textContent = e.total + (e.total === 1 ? ' scheda' : ' schede');
      a.appendChild(name);
      a.appendChild(counts);
      a.appendChild(total);
      frag.appendChild(a);
    });
    var head2 = document.createElement('div');
    head2.className = 'ps-head';
    head2.textContent = 'Schede';
    frag.appendChild(head2);
    return frag;
  };
})();
