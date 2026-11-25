"""Gadda's correspondence → checkable tables, ready for the RDF conversion
(LetterSampo-style model: Letter, Actor, Place, Tie).

The senders file is the backbone: every correspondent in it is an actor with
their whole correspondence (a Tie); the letters file adds the individual
letters, attached to those ties.

Reads (never writes) the two Excel files in OneDrive and the corrected
OpenRefine exports, applies the agreed corrections, and writes:
  ids.csv           the OpenGadda ids (kept between runs: an existing name keeps
                    its number, a new one gets the next free number)
  people.csv        every actor (person or organisation), with id, VIAF/Wikidata
                    and statistics
  ties.csv          one row per correspondence with Gadda
  letters.csv       one row per letter (several recipients → one row each,
                    linked by `document`)
  places.csv        every place in the letters: city / address / GeoNames, with id
  sources.csv       where the information comes from: the editions the letters
                    are published in, and the two archives (Bonsanti, Liberati)
  report.md         what is missing or needs a decision

Authorities: ONLY the corrected exports in lod/openrefine/tables (the VIAF ids in
mittenti_enriched.json proved unreliable). viaf_to_check.csv is read only once
VIAF_CHECKED below is set to True, i.e. after the user has checked it.

Run:  python3 lod/letters/build_letters_table.py
"""
import re
import csv
import collections
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
LOD = HERE.parent
ONEDRIVE = Path('/Users/martinapensalfini/Library/CloudStorage/OneDrive-AlmaMaterStudiorumUniversitàdiBologna/dataset')
LETTERS_XLSX = ONEDRIVE / 'lettere.xlsx'
SENDERS_XLSX = ONEDRIVE / 'dati_mittenti_Gadda.xlsx'
TABLES = LOD / 'openrefine' / 'tables'
IDS_CSV = HERE / 'ids.csv'
VIAF_CHECK_CSV = HERE / 'viaf_to_check.csv'
VIAF_CHECKED = False  # set to True once viaf_to_check.csv has been gone through

GADDA = 'Gadda Carlo Emilio'
ITEMS_JSON = LOD.parent / 'code_updated' / 'items.json'  # only to link editions to their record on the site
SITE_RECORD = 'https://angstigone.github.io/opengadda/code_updated/detail.html?id='
# the senders-file category that is never a single person ("Editori, riviste e
# quotidiani" also holds people such as Garzanti Livio, so it doesn't decide)
ORG_CATEGORIES = {'Istituzioni, associazioni ed enti pubblici'}

# --- agreed corrections (2026-11-25) ------------------------------------------
DATE_FIX = {
    'Let1511': '1959-07-24',  # "2959-07-24" in the Excel: typo for 1959
    'Let1672': None,          # "monda" in the Excel: date unknown for now
}
# places with two GeoNames ids: keep the city (populated place), not the
# administrative area — checked on geonames.org
CITY_ID = {
    frozenset({'6542283', '3173435'}): '3173435',  # Milan
    frozenset({'2968815', '2988507'}): '2988507',  # Paris
    frozenset({'6453507', '2983013'}): '2983013',  # Romans
    frozenset({'6541857', '3176885'}): '3176885',  # Foggia
    frozenset({'7287487', '2658112'}): '2658112',  # Visp
    frozenset({'6541860', '2525764'}): '2525764',  # Agrigento
}


def clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ''
    return re.sub(r'\s+', ' ', str(v)).strip()


def key(name):
    return re.sub(r'\s+', ' ', str(name).replace(',', '')).strip().lower()


def split_names(v):
    return [n for n in (clean(x) for x in clean(v).split(';')) if n and n != '?']


# --- OpenGadda ids, stable between runs --------------------------------------
PREFIX = {'person': 'p', 'place': 'pl'}
ids = {}  # (kind, key) → id
if IDS_CSV.exists():
    with open(IDS_CSV, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            ids[(r['kind'], r['key'])] = r['id']
labels = {}


def og_id(kind, k, label):
    labels[(kind, k)] = label
    if (kind, k) not in ids:
        used = [int(re.sub(r'\D', '', v)) for (kd, _), v in ids.items() if kd == kind]
        ids[(kind, k)] = f'{PREFIX[kind]}{(max(used) + 1 if used else 1):04d}'
    return ids[(kind, k)]


# --- corrected authorities ------------------------------------------------------
names = pd.read_csv(TABLES / 'names-in-items-csv.csv', dtype=str).fillna('')
VIAF_COL = 'VIAF cluster ID'
# per letter occurrence (letter id, name as written) → row
by_item = {}
# per name, over the whole dataset → VIAF ids and type
viaf_by_name = collections.defaultdict(set)
type_by_name = {}
for r in names.to_dict('records'):
    for n in {r['name_as_written'], r['name_plain']}:
        k = key(n)
        if r['category'] == 'letter':
            by_item.setdefault((r['item_id'], k), r)
        if r[VIAF_COL]:
            viaf_by_name[k].add(r[VIAF_COL])
        if r['type'] and k not in type_by_name:
            type_by_name[k] = r['type']

people_tab = pd.read_csv(TABLES / 'people-csv.csv', dtype=str).fillna('')
extra = {}
for r in people_tab.to_dict('records'):
    k = key(r['name'])
    extra[k] = r
    if r[VIAF_COL]:
        viaf_by_name[k].add(r[VIAF_COL])

# the user's checked list (only once VIAF_CHECKED is True)
checked = {}
if VIAF_CHECKED and VIAF_CHECK_CSV.exists():
    with open(VIAF_CHECK_CSV, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            v = clean(r.get('your_viaf')) or clean(r.get('old_viaf'))
            checked[key(r['correspondent'])] = v  # '' = no VIAF

place_rows = pd.read_csv(TABLES / 'places-csv.csv', dtype=str).fillna('')
place_auth = {}
cur = None
for r in place_rows.to_dict('records'):
    if r['field']:
        cur = {'value': clean(r['value']), 'city': clean(r['city']),
               'ids': [r['GeoNames ID']] if r['GeoNames ID'] else [], 'address': clean(r['address'])}
        if r['field'] in ('luogo_di_invio', 'luogo_destinatario'):
            place_auth.setdefault(cur['value'], cur)
    elif cur is not None and r['GeoNames ID']:
        cur['ids'].append(r['GeoNames ID'])


def place_of(raw):
    raw = clean(raw)
    if not raw:
        return {'raw': '', 'id': '', 'city': '', 'address': '', 'geonames': '', 'city_id': ''}
    a = place_auth.get(raw)
    city = a['city'] if a else ''
    gid = (CITY_ID.get(frozenset(a['ids']), a['ids'][0]) if a and a['ids'] else '')
    address = a['address'] if a else ''
    # the city is a place; an address is its own place, within the city
    city_key = gid or key(city or raw)
    city_id = og_id('place', city_key, city or raw)
    pid = og_id('place', f'{city_key}|{key(address)}', f'{city}, {address}') if address else city_id
    return {'raw': raw, 'id': pid, 'city': city, 'address': address, 'geonames': gid, 'city_id': city_id}


# --- actors -----------------------------------------------------------------------
people = {}


def actor(name, category=''):
    k = key(name)
    p = people.get(k)
    if p is None:
        viafs = sorted(viaf_by_name.get(k, set()))
        if k in checked:
            viafs = [checked[k]] if checked[k] else []
        x = extra.get(k, {})
        typ = 'organization' if category in ORG_CATEGORIES else (type_by_name.get(k) or 'person')
        p = people[k] = {
            'id': og_id('person', k, name), 'name': name, 'type': typ,
            'viaf': ' | '.join(viafs), 'wikidata': x.get('wikidata_id', ''),
            'birth': x.get('birth', ''), 'death': x.get('death', ''), 'category': category,
            'known_total': 0, 'known_bonsanti': 0, 'known_liberati': 0, 'known_range': '',
            'described_sent': 0, 'described_received': 0, 'first_year': '', 'last_year': '',
        }
    if category and not p['category']:
        p['category'] = category
        if category in ORG_CATEGORIES:
            p['type'] = 'organization'
    return p


actor(GADDA)

# the senders file: every correspondence with Gadda
ties = {}
for r in pd.read_excel(SENDERS_XLSX).to_dict('records'):
    name = clean(r['Mittenti'])
    if not name:
        continue
    p = actor(name, clean(r['Tipologia']))
    t = ties.setdefault(p['id'], {'tie': f't{p["id"][1:]}', 'correspondent_id': p['id'], 'correspondent': name,
                                  'category': clean(r['Tipologia']), 'total': 0, 'bonsanti': 0, 'liberati': 0,
                                  'range': [], 'range_bonsanti': [], 'range_liberati': [], 'rows': 0})
    t['rows'] += 1  # five people are split over two rows: merged here
    for f, col in (('total', 'Numero dei pezzi'), ('bonsanti', 'Archivio Bonsanti'), ('liberati', 'Archivio Liberati')):
        if not pd.isna(r[col]):
            t[f] += int(r[col])
    for f, col in (('range', 'Estremi cronologici'), ('range_bonsanti', 'Estremi cronologici Archivio Bonsanti'),
                   ('range_liberati', 'Estremi cronologici Archivio Liberati')):
        if clean(r[col]):
            t[f].append(clean(r[col]))


# --- letters ------------------------------------------------------------------------
def date_of(letter_id, v):
    """→ (start, end, original text, precision)"""
    if letter_id in DATE_FIX:
        d = DATE_FIX[letter_id]
        return (d, d, clean(v), 'day') if d else ('', '', clean(v), 'unknown')
    if hasattr(v, 'strftime'):
        d = v.strftime('%Y-%m-%d')
        return d, d, '', 'day'
    text = clean(v)
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if m:  # e.g. "16/12/1942 (?)": that day, marked uncertain
        d = f'{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}'
        return d, d, text, 'day-uncertain'
    return '', '', text, 'unknown'


def letter_viaf(name, letter_id):
    """the VIAF reconciled for this very occurrence, if any"""
    occ = by_item.get((letter_id, key(name)))
    return occ[VIAF_COL] if occ else ''


# --- sources: where each letter and correspondence is documented ------------------
# an edition (published letters) or an archival collection (unpublished ones,
# and the two inventories that count each correspondence). Editions keep their
# sigla as id; each gets a link to its primary-bibliography record on the site
# when there is one (secondary-bibliography items that discuss a correspondence
# carry the sigla too, but they are not the edition).
import json
edition_record = collections.defaultdict(list)
for it in json.load(open(ITEMS_JSON, encoding='utf-8')):
    if it.get('corpus_lettere') and it.get('category') == 'primary bibliography':
        edition_record[it['corpus_lettere']].append(it['id'])
ARCHIVES = {
    'archivio a. bonsanti': ('archivio-bonsanti', 'Archivio A. Bonsanti'),
    'archivio bonsanti': ('archivio-bonsanti', 'Archivio A. Bonsanti'),
    'archivio liberati': ('archivio-liberati', 'Archivio Liberati'),
}
sources = {}


def edition_source(sigla, reference):
    if not sigla:
        return ''
    s = sources.setdefault(sigla, {'id': sigla, 'type': 'edition', 'sigla': sigla, 'label': reference,
                                   'opengadda_record': ' '.join(SITE_RECORD + i for i in sorted(edition_record.get(sigla, []))),
                                   'letters': 0})
    if reference and not s['label']:
        s['label'] = reference
    return s['id']


def archive_source(name):
    sid, label = ARCHIVES.get(key(name), (re.sub(r'\W+', '-', key(name)).strip('-'), clean(name)))
    sources.setdefault(sid, {'id': sid, 'type': 'archival collection', 'sigla': '', 'label': label,
                             'opengadda_record': '', 'letters': 0})
    return sid


letters, problems = [], collections.defaultdict(list)
for r in pd.read_excel(LETTERS_XLSX).to_dict('records'):
    lid = clean(r['Id'])
    senders = split_names(r['Mittente'])
    recipients = split_names(r['Destinatario']) or ['']
    start, end, date_text, precision = date_of(lid, r['Data'])
    pfrom, pto = place_of(r['Luogo di invio']), place_of(r['Luogo destinatario'])
    year = start[:4]
    sender_actors = [actor(s) for s in senders]
    for p in sender_actors:  # counted once per document, even when it is split
        p['described_sent'] += 1
    for i, rcp in enumerate(recipients, 1):
        rid = lid if len(recipients) == 1 else f'{lid}-{i}'
        ra = actor(rcp) if rcp else None
        if ra:
            ra['described_received'] += 1
        # the correspondence this letter belongs to: the person other than Gadda
        others = [p for p in sender_actors + ([ra] if ra else []) if p['name'] != GADDA]
        for p in others:
            if year:
                p['first_year'] = min(filter(None, [p['first_year'], year]))
                p['last_year'] = max(filter(None, [p['last_year'], year]))
            ties.setdefault(p['id'], {'tie': f't{p["id"][1:]}', 'correspondent_id': p['id'], 'correspondent': p['name'],
                                      'category': clean(r['Genere']), 'total': 0, 'bonsanti': 0, 'liberati': 0,
                                      'range': [], 'range_bonsanti': [], 'range_liberati': [], 'rows': 0})
        letters.append({
            'letter': rid, 'document': lid,
            'sender_ids': '; '.join(p['id'] for p in sender_actors), 'senders': '; '.join(senders),
            'recipient_id': ra['id'] if ra else '', 'recipient': rcp,
            'date_start': start, 'date_end': end, 'date_text': date_text, 'date_precision': precision,
            'from_place_id': pfrom['id'], 'from_raw': pfrom['raw'], 'from_city': pfrom['city'],
            'from_address': pfrom['address'], 'from_geonames': pfrom['geonames'],
            'to_place_id': pto['id'], 'to_raw': pto['raw'], 'to_city': pto['city'],
            'to_address': pto['address'], 'to_geonames': pto['geonames'],
            'edition_sigla': clean(r['Opera']), 'edition': clean(r['Sigla sciolta']),
            'archive': clean(r['Archivio']),
            # published letters: their edition; unpublished ones: the archive holding them
            'source_id': edition_source(clean(r['Opera']), clean(r['Sigla sciolta'])) or
                         (archive_source(r['Archivio']) if clean(r['Archivio']) else ''),
            'tie_ids': '; '.join(ties[p['id']]['tie'] for p in others),
            'category': clean(r['Genere']),
        })
        if not letters[-1]['source_id']:
            problems['letter without source'].append(lid)
        if not senders:
            problems['letter without sender'].append(lid)
        if not rcp:
            problems['letter without recipient'].append(lid)
        if precision == 'unknown':
            problems['letter without date'].append(lid)
        for p in (pfrom, pto):
            if p['raw'] and not p['geonames']:
                problems[f'place without GeoNames id: {p["raw"]}'].append(lid)
        for n in senders + ([rcp] if rcp else []):
            v = letter_viaf(n, lid)
            if v and v not in people[key(n)]['viaf']:
                problems[f'VIAF of {n} differs in this letter ({v})'].append(lid)

# sources of each correspondence: the inventories that count it, plus the
# editions/archives of its individual letters; an actor's sources are those of
# their correspondences (Gadda: of every letter)
for x in letters:
    if i_ := x['source_id']:
        sources[i_]['letters'] += 1 if x['letter'] == x['document'] or x['letter'].endswith('-1') else 0
tie_sources = collections.defaultdict(set)
for t in ties.values():
    if t['bonsanti']:
        tie_sources[t['tie']].add(archive_source('Archivio Bonsanti'))
    if t['liberati']:
        tie_sources[t['tie']].add(archive_source('Archivio Liberati'))
for x in letters:
    for tid in filter(None, x['tie_ids'].split('; ')):
        if x['source_id']:
            tie_sources[tid].add(x['source_id'])
for t in ties.values():
    t['source_ids'] = '; '.join(sorted(tie_sources[t['tie']]))
actor_sources = collections.defaultdict(set)
for t in ties.values():
    actor_sources[t['correspondent_id']] |= tie_sources[t['tie']]
for x in letters:
    if x['source_id']:
        for pid in filter(None, x['sender_ids'].split('; ') + [x['recipient_id']]):
            actor_sources[pid].add(x['source_id'])
for p in people.values():
    p['source_ids'] = '; '.join(sorted(actor_sources[p['id']]))
    if not p['source_ids']:
        problems['actor without source'].append(p['id'])

# statistics from the senders file onto each actor
for t in ties.values():
    p = next(p for p in people.values() if p['id'] == t['correspondent_id'])
    p['known_total'], p['known_bonsanti'], p['known_liberati'] = t['total'], t['bonsanti'], t['liberati']
    p['known_range'] = ' | '.join(t['range'])
    t['described_letters'] = p['described_sent'] + p['described_received']

# possible duplicates: undated, same sender, recipient and edition
seen = collections.defaultdict(set)
for x in letters:
    if x['date_precision'] == 'unknown':
        seen[(x['senders'], x['recipient'], x['edition_sigla'])].add(x['document'])
dupes = [sorted(v) for v in seen.values() if len(v) > 1]


# --- write ---------------------------------------------------------------------------
def write(path, rows, fields):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


write(IDS_CSV, [{'kind': kd, 'key': k, 'id': v, 'label': labels.get((kd, k), '')}
                for (kd, k), v in sorted(ids.items(), key=lambda kv: (kv[0][0], kv[1]))],
      ['kind', 'key', 'id', 'label'])
write(HERE / 'people.csv', sorted(people.values(), key=lambda p: p['id']), list(next(iter(people.values()))))
write(HERE / 'ties.csv', [dict(t, range=' | '.join(t['range']), range_bonsanti=' | '.join(t['range_bonsanti']),
                               range_liberati=' | '.join(t['range_liberati'])) for t in sorted(ties.values(), key=lambda t: t['tie'])],
      ['tie', 'correspondent_id', 'correspondent', 'category', 'total', 'bonsanti', 'liberati',
       'range', 'range_bonsanti', 'range_liberati', 'rows', 'described_letters', 'source_ids'])
write(HERE / 'sources.csv', sorted(sources.values(), key=lambda s: (s['type'], s['id'])),
      ['id', 'type', 'sigla', 'label', 'opengadda_record', 'letters'])
write(HERE / 'letters.csv', letters, list(letters[0]))
places = {}
for x in letters:
    for side in ('from', 'to'):
        if x[f'{side}_raw']:
            pl = places.setdefault(x[f'{side}_raw'], {'id': x[f'{side}_place_id'], 'raw': x[f'{side}_raw'],
                                                       'city': x[f'{side}_city'], 'address': x[f'{side}_address'],
                                                       'geonames': x[f'{side}_geonames'], 'letters': 0})
            pl['letters'] += 1
write(HERE / 'places.csv', sorted(places.values(), key=lambda p: -p['letters']),
      ['id', 'raw', 'city', 'address', 'geonames', 'letters'])

# --- report ----------------------------------------------------------------------------
P = list(people.values())
in_senders = {t['correspondent_id'] for t in ties.values() if t['rows']}
not_in_senders = [p for p in P if p['name'] != GADDA and p['id'] not in in_senders
                  and (p['described_sent'] or p['described_received'])]
lines = ['# Gadda\'s correspondence: what needs checking', '',
         f'- actors: {len(P)} ({sum(p["type"] == "organization" for p in P)} organisations); '
         f'with VIAF {sum(1 for p in P if p["viaf"])}, with Wikidata {sum(1 for p in P if p["wikidata"])}',
         f'- correspondences (ties): {len(ties)}, of which {sum(1 for t in ties.values() if t["described_letters"])} '
         f'with individual letters; merged from two rows: '
         + ', '.join(t['correspondent'] for t in ties.values() if t['rows'] > 1),
         f'- letters: {len(letters)} rows from {len({x["document"] for x in letters})} documents',
         f'- places: {len(places)} as written, {sum(1 for p in places.values() if p["geonames"])} with GeoNames',
         f'- VIAF list checked by the user: {"yes" if VIAF_CHECKED else "not yet (viaf_to_check.csv not used)"}', '']
lines += ['## Actors with two VIAF ids (choose one)', '']
lines += [f'- {p["name"]} ({p["id"]}): {p["viaf"]}' for p in P if '|' in p['viaf']] or ['- none']
lines += ['', '## Possible duplicate letters (undated, same sender, recipient and edition)', '']
lines += [f'- {", ".join(v)}' for v in dupes] or ['- none']
lines += ['', '## People in the letters with no row in dati_mittenti_Gadda.xlsx (spelling difference, or missing)', '']
lines += [f'- {p["name"]} ({p["id"]}, {p["described_sent"] + p["described_received"]} letters)'
          for p in sorted(not_in_senders, key=lambda p: p['name'])] or ['- none']
for what, lids in sorted(problems.items()):
    lids = sorted(set(lids), key=lambda s: int(re.sub(r'\D', '', s) or 0))
    lines += ['', f'## {what}: {len(lids)}', '', '- ' + ', '.join(lids)]
(HERE / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines[:8]))
