// Image credits — shows the copyright line from img_credits.json for every
// picture loaded from img/: in small print under the large covers (record
// page, work cards on the Opere page) and as a hover tooltip everywhere else.
// Images whose line is empty show nothing.
(function () {
  const CAPTIONED = ['record-cover', 'opera-thumb', 'work-thumb'];
  let credits = null;
  const pending = [];

  const style = document.createElement('style');
  style.textContent =
    '.img-credit-fig { margin:0; display:flex; flex-direction:column; gap:3px; flex-shrink:0; }' +
    '.img-credit-fig.is-float { float:right; margin:0 0 1rem 1.25rem; }' +
    '.img-credit-fig.is-float > img { float:none; margin:0; }' +
    '.img-credit { font-family:"DM Mono",monospace; font-size:9px; line-height:1.35; letter-spacing:0.02em; color:var(--muted,#7a7268); overflow-wrap:anywhere; }';
  document.head.appendChild(style);

  function fileOf(img) {
    const m = (img.getAttribute('src') || '').match(/(?:^|\/)img\/([^?#]+)$/);
    return m ? decodeURIComponent(m[1]) : null;
  }

  function apply(img) {
    const file = fileOf(img);
    if (!file) return;
    const text = (credits[file] || '').trim();
    const fig = img.parentElement && img.parentElement.classList.contains('img-credit-fig') ? img.parentElement : null;
    if (!text) { img.removeAttribute('title'); if (fig) fig.querySelector('.img-credit').textContent = ''; return; }
    img.title = text;
    if (!CAPTIONED.some(c => img.classList.contains(c))) return;
    if (fig) { fig.querySelector('.img-credit').textContent = text; return; }
    const f = document.createElement('figure');
    f.className = 'img-credit-fig' + (getComputedStyle(img).float !== 'none' ? ' is-float' : '');
    f.style.width = img.getBoundingClientRect().width + 'px';
    img.replaceWith(f);
    f.appendChild(img);
    const cap = document.createElement('figcaption');
    cap.className = 'img-credit';
    cap.textContent = text;
    f.appendChild(cap);
  }

  // `load` doesn't bubble, but it can be caught on the way down.
  document.addEventListener('load', e => {
    const img = e.target;
    if (img.tagName !== 'IMG') return;
    credits ? apply(img) : pending.push(img);
  }, true);

  fetch('img_credits.json').then(r => r.json()).catch(() => ({})).then(c => {
    credits = c || {};
    pending.splice(0).forEach(apply);
    document.querySelectorAll('img').forEach(img => { if (img.complete && img.naturalWidth) apply(img); });
  });
})();
