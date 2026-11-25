"""Letters → one checkable table, following the LetterSampo-style mapping.

Reads (never writes) the two Excel files in OneDrive and the OpenRefine
authority exports, applies the agreed corrections, and writes:
  letters.csv       one row per letter (letters with several recipients are
                    split into one row per recipient, linked by `document`)
  people.csv        every person/organisation in the letters, with ids
  places.csv        every place value in the letters, with city / address / GeoNames
  ties.csv          one row per correspondent (overall correspondence with Gadda)
  report.md         what is missing or needs a decision

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
LIFESPANS = LOD.parent / 'storyline' / 'people_birth_death.json'

GADDA = 'Gadda Carlo Emilio'

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
    return re.sub(r'\s+', ' ', name.replace(',', '')).strip().lower()


def split_names(v):
    return [n for n in (clean(x) for x in clean(v).split(';')) if n and n != '?']


# --- authority files ----------------------------------------------------------
names = pd.read_csv(TABLES / 'names-in-items-csv.csv', dtype=str).fillna('')
names = names[names.category == 'letter']
# (letter id, name) → VIAF / type, as reconciled per occurrence in OpenRefine
# matched on the spelling as written (name_plain now holds VIAF's form of the name)
by_item = {}
for r in names.itertuples():
    for n in {r.name_as_written, r.name_plain}:
        by_item.setdefault((r.item_id, key(n)), r)
# name → VIAF / type over all letters (to fill names whose occurrence has none)
by_name = {}
for r in names.itertuples():
    for n in {r.name_as_written, r.name_plain}:
        e = by_name.setdefault(key(n), {'viaf': '', 'type': ''})
        if r._7 and not e['viaf']:  # 'VIAF cluster ID'
            e['viaf'] = r._7
        if r.type and not e['type']:
            e['type'] = r.type

people_tab = pd.read_csv(TABLES / 'people-csv.csv', dtype=str).fillna('')
people_extra = {key(r.name): r for r in people_tab.itertuples()}

place_rows = pd.read_csv(TABLES / 'places-csv.csv', dtype=str).fillna('')
place_auth = {}
cur = None
for r in place_rows.itertuples():
    if r.field:
        cur = {'field': r.field, 'value': clean(r.value), 'city': clean(r.city),
               'ids': [r._4] if r._4 else [], 'address': clean(r.address)}
        if r.field in ('luogo_di_invio', 'luogo_destinatario'):
            place_auth.setdefault(cur['value'], cur)
    elif cur is not None and r._4:
        cur['ids'].append(r._4)


def place_of(raw):
    raw = clean(raw)
    if not raw:
        return {'raw': '', 'city': '', 'geonames': '', 'address': ''}
    a = place_auth.get(raw)
    if not a:
        return {'raw': raw, 'city': '', 'geonames': '', 'address': ''}
    ids = a['ids']
    gid = CITY_ID.get(frozenset(ids), ids[0]) if ids else ''
    return {'raw': raw, 'city': a['city'], 'geonames': gid, 'address': a['address']}


# --- dates --------------------------------------------------------------------
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


# --- letters --------------------------------------------------------------------
L = pd.read_excel(LETTERS_XLSX)
letters, problems = [], collections.defaultdict(list)
people = {}


def person(name, letter_id, role):
    k = key(name)
    occ = by_item.get((letter_id, k))
    viaf = (occ._7 if occ is not None else '') or by_name.get(k, {}).get('viaf', '')
    typ = (occ.type if occ is not None else '') or by_name.get(k, {}).get('type', '') or 'person'
    p = people.setdefault(k, {'name': name, 'type': typ, 'viaf': viaf, 'wikidata': '',
                              'birth': '', 'death': '', 'sent': 0, 'received': 0})
    if viaf and not p['viaf']:
        p['viaf'] = viaf
    x = people_extra.get(k)
    if x is not None:
        p['wikidata'] = p['wikidata'] or x.wikidata_id
        p['birth'] = p['birth'] or x.birth
        p['death'] = p['death'] or x.death
    p['sent' if role == 'sender' else 'received'] += 1
    return p


for r in L.itertuples():
    lid = clean(r.Id)
    senders = split_names(r.Mittente)
    recipients = split_names(r.Destinatario) or ['']
    start, end, date_text, precision = date_of(lid, r.Data)
    pfrom, pto = place_of(r._6), place_of(r._7)  # Luogo di invio / destinatario
    for s in senders:  # counted once per document, even when it is split
        person(s, lid, 'sender')
    for i, rcp in enumerate(recipients, 1):
        rid = lid if len(recipients) == 1 else f'{lid}-{i}'
        if rcp:
            person(rcp, lid, 'recipient')
        others = [n for n in senders + [rcp] if n and n != GADDA]
        letters.append({
            'letter': rid, 'document': lid,
            'senders': '; '.join(senders),
            'sender_viaf': '; '.join(people[key(s)]['viaf'] for s in senders),
            'recipient': rcp,
            'recipient_viaf': people[key(rcp)]['viaf'] if rcp else '',
            'date_start': start, 'date_end': end, 'date_text': date_text, 'date_precision': precision,
            'from_raw': pfrom['raw'], 'from_city': pfrom['city'], 'from_address': pfrom['address'], 'from_geonames': pfrom['geonames'],
            'to_raw': pto['raw'], 'to_city': pto['city'], 'to_address': pto['address'], 'to_geonames': pto['geonames'],
            'edition_sigla': clean(r.Opera), 'edition': clean(r._9),  # Sigla sciolta
            'archive': clean(r.Archivio),
            'tie': '; '.join(others),
            'category': clean(r.Genere),
        })
        if not senders:
            problems['letter without sender'].append(lid)
        if not rcp:
            problems['letter without recipient'].append(lid)
        if precision == 'unknown':
            problems['letter without date'].append(lid)
        for side, p in (('from', pfrom), ('to', pto)):
            if p['raw'] and not p['geonames']:
                problems[f'place without GeoNames id ({p["raw"]})'].append(lid)

# possible duplicates: same sender, recipient, no date
seen = collections.defaultdict(list)
for x in letters:
    if x['date_precision'] == 'unknown':
        seen[(x['senders'], x['recipient'], x['edition_sigla'])].append(x['document'])
dupes = [v for v in seen.values() if len(set(v)) > 1]

# --- ties: one per correspondent, from the senders Excel ---------------------
M = pd.read_excel(SENDERS_XLSX)
ties = {}
for r in M.itertuples():
    name = clean(r.Mittenti)
    if not name:
        continue
    t = ties.setdefault(key(name), {'correspondent': name, 'total': 0, 'bonsanti': 0, 'liberati': 0,
                                   'range': [], 'range_bonsanti': [], 'range_liberati': [], 'category': clean(r.Tipologia),
                                   'rows': 0})
    t['rows'] += 1  # five people are split over two rows: merged here
    for f, col in (('total', r._4), ('bonsanti', r._2), ('liberati', r._3)):
        if not pd.isna(col):
            t[f] += int(col)
    for f, col in (('range', r._5), ('range_bonsanti', r._11), ('range_liberati', r._12)):
        if clean(col):
            t[f].append(clean(col))

described = collections.Counter()
for x in letters:
    for n in x['tie'].split('; '):
        if n:
            described[key(n)] += 1

# --- write --------------------------------------------------------------------
def write(name, rows, fields):
    with open(HERE / name, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


write('letters.csv', letters, list(letters[0]))
write('people.csv', sorted(people.values(), key=lambda p: p['name']),
      ['name', 'type', 'viaf', 'wikidata', 'birth', 'death', 'sent', 'received'])
place_values = collections.Counter(v for x in letters for v in (x['from_raw'], x['to_raw']) if v)
write('places.csv', [dict(place_of(v), count=n) for v, n in place_values.most_common()],
      ['raw', 'city', 'address', 'geonames', 'count'])
write('ties.csv', [{**{k: v for k, v in t.items() if k not in ('range', 'range_bonsanti', 'range_liberati')},
                    'range': ' | '.join(t['range']), 'range_bonsanti': ' | '.join(t['range_bonsanti']),
                    'range_liberati': ' | '.join(t['range_liberati']),
                    'described_letters': described.get(k, 0)} for k, t in sorted(ties.items())],
      ['correspondent', 'category', 'total', 'bonsanti', 'liberati', 'range', 'range_bonsanti', 'range_liberati', 'rows', 'described_letters'])

no_tie = sorted({n for n in described if n not in ties})
lines = ['# Letters: what needs checking', '',
         f'- letters (rows, after splitting several recipients): {len(letters)} from {L.shape[0]} documents',
         f'- people: {len(people)}, with VIAF {sum(1 for p in people.values() if p["viaf"])}, '
         f'with Wikidata {sum(1 for p in people.values() if p["wikidata"])}, organisations {sum(1 for p in people.values() if p["type"] == "organization")}',
         f'- correspondences (ties): {len(ties)}; merged from two rows: '
         + ', '.join(t['correspondent'] for t in ties.values() if t['rows'] > 1), '']
lines += ['## Possible duplicates (undated, same sender, recipient and edition)', '']
lines += [f'- {", ".join(sorted(set(v)))}' for v in dupes] or ['- none']
lines += ['', '## People in the letters with no correspondence row in dati_mittenti_Gadda.xlsx', '']
lines += [f'- {people[n]["name"]} ({described[n]} letters)' for n in no_tie] or ['- none']
lines += ['', '## People without VIAF (they get an OpenGadda id)', '']
lines += [f'- {p["name"]} ({p["sent"] + p["received"]} letters)'
          for p in sorted(people.values(), key=lambda p: -(p['sent'] + p['received'])) if not p['viaf'] and p['name'] != GADDA]
for what, ids in sorted(problems.items()):
    lines += ['', f'## {what}: {len(set(ids))}', '', '- ' + ', '.join(sorted(set(ids), key=lambda s: int(re.sub(r"\D", "", s) or 0)))]
(HERE / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines[:6]))
