/**
 * Offline GSTIN / PAN / Udyam parsing, ported from backend/app/shared/india/identifiers.py so the check desk can
 * give feedback on every keystroke. This only proves a number is well-formed. Whether it is active needs the GST
 * registry, and the backend is still called on submit.
 */

export const STATE_CODES: Record<string, string> = {
  '01': 'Jammu and Kashmir', '02': 'Himachal Pradesh', '03': 'Punjab', '04': 'Chandigarh', '05': 'Uttarakhand', '06': 'Haryana',
  '07': 'Delhi', '08': 'Rajasthan', '09': 'Uttar Pradesh', '10': 'Bihar', '11': 'Sikkim', '12': 'Arunachal Pradesh', '13': 'Nagaland',
  '14': 'Manipur', '15': 'Mizoram', '16': 'Tripura', '17': 'Meghalaya', '18': 'Assam', '19': 'West Bengal', '20': 'Jharkhand',
  '21': 'Odisha', '22': 'Chhattisgarh', '23': 'Madhya Pradesh', '24': 'Gujarat', '26': 'Dadra and Nagar Haveli and Daman and Diu',
  '27': 'Maharashtra', '28': 'Andhra Pradesh (before division)', '29': 'Karnataka', '30': 'Goa', '31': 'Lakshadweep', '32': 'Kerala',
  '33': 'Tamil Nadu', '34': 'Puducherry', '35': 'Andaman and Nicobar Islands', '36': 'Telangana', '37': 'Andhra Pradesh', '38': 'Ladakh',
  '97': 'Other Territory', '99': 'Centre Jurisdiction',
};

export const PAN_HOLDER_TYPES: Record<string, string> = {
  P: 'Individual', C: 'Company', H: 'Hindu Undivided Family', F: 'Firm / LLP', A: 'Association of Persons', B: 'Body of Individuals',
  T: 'Trust', L: 'Local Authority', J: 'Artificial Juridical Person', G: 'Government',
};

const CODEPOINT = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';

export function gstinCheckChar(first14: string): string {
  let total = 0;
  for (let i = 0; i < first14.length; i++) {
    const val = CODEPOINT.indexOf(first14[i]);
    const prod = val * (i % 2 === 0 ? 1 : 2);
    total += Math.floor(prod / 36) + (prod % 36);
  }
  return CODEPOINT[(36 - (total % 36)) % 36];
}

/** Upper-case, drop spaces/hyphens/anything that is not a letter or digit. */
export const clean = (raw: string): string => raw.toUpperCase().replace(/[^A-Z0-9]/g, '');

export type Kind = 'gstin' | 'pan' | 'udyam' | 'cin' | 'llpin' | 'tan' | 'ifsc' | 'iec' | 'fssai' | 'esic' | 'pf';
export type SegStatus = 'ok' | 'bad' | 'partial' | 'empty';

export interface Seg {
  id: string;
  text: string;
  size: number;
  status: SegStatus;
  label: string;   // shown under the strip, e.g. "24 Gujarat"
  hint: string;    // what goes here, shown while empty
}

export interface Parsed {
  kind: Kind | null;
  value: string;
  segs: Seg[];
  complete: boolean;
  allOk: boolean;
  summary: string | null;   // the one-line result once complete and well-formed
}

const isLetters = (s: string) => /^[A-Z]*$/.test(s);
const isDigits = (s: string) => /^\d*$/.test(s);

function seg(id: string, value: string, start: number, size: number, hint: string, judge: (t: string) => { status: SegStatus; label: string }): Seg {
  const text = value.slice(start, start + size);
  if (!text) return { id, text, size, status: 'empty', label: hint, hint };
  return { id, text, size, hint, ...judge(text) };
}

/** Numbers with no registry: we only know their shape. Mirrors `identify` in the backend. */
export function detectOtherKind(v: string): Kind | null {
  if (v.length === 21 && 'LU'.includes(v[0])) return 'cin';
  if (/^[A-Z]{3}\d{4}$/.test(v)) return 'llpin';
  if (v.length === 11 && /^[A-Z]{4}0/.test(v)) return 'ifsc';
  if (/^[A-Z]{4}\d{5}[A-Z]$/.test(v)) return 'tan';
  if (/^\d{10}$/.test(v)) return 'iec';
  if (/^\d{14}$/.test(v)) return 'fssai';
  if (/^\d{17}$/.test(v)) return 'esic';
  if ((v.length === 12 || v.length === 15) && /^[A-Z]{5}\d{7}(\d{3})?$/.test(v)) return 'pf';
  return null;
}

export function detectKind(v: string): Kind | null {
  if (!v) return null;
  const other = detectOtherKind(v);
  if (other) return other;
  if (/^\d/.test(v)) return 'gstin';
  if (v.startsWith('UDYAM') && !(v.length === 10 && /^[A-Z]{5}\d{4}[A-Z]$/.test(v))) return 'udyam';
  if (/^[A-Z]/.test(v)) return 'pan';
  return 'gstin';
}

function parseGstin(v: string): Parsed {
  const state = seg('state', v, 0, 2, 'State code, 2 digits', (t) => {
    if (!isDigits(t)) return { status: 'bad', label: 'The first 2 characters are a state code (digits)' };
    if (t.length < 2) return { status: 'partial', label: 'State code' };
    return STATE_CODES[t] ? { status: 'ok', label: `${t} ${STATE_CODES[t]}` } : { status: 'bad', label: `${t} is not a state code` };
  });
  const pan = seg('pan', v, 2, 10, 'PAN, 10 characters', (t) => {
    const shape = 'AAAAA9999A';
    for (let i = 0; i < t.length; i++) {
      const ok = i < 5 || i === 9 ? /[A-Z]/.test(t[i]) : /\d/.test(t[i]);
      if (!ok) return { status: 'bad', label: `PAN should look like ${shape} (5 letters, 4 digits, 1 letter)` };
    }
    if (t.length < 10) return { status: 'partial', label: `PAN ${t}...` };
    const holder = PAN_HOLDER_TYPES[t[3]];
    return holder ? { status: 'ok', label: `PAN ${t} - ${holder}` } : { status: 'bad', label: `PAN type letter '${t[3]}' is not a real holder type` };
  });
  const entity = seg('entity', v, 12, 1, 'Entity number, 1-9 or A-Z', (t) =>
    /^[1-9A-Z]$/.test(t) ? { status: 'ok', label: `Entity ${t} (registration number under this PAN)` } : { status: 'bad', label: 'Entity number must be 1-9 or a letter' });
  const z = seg('z', v, 13, 1, 'Always Z', (t) => (t === 'Z' ? { status: 'ok', label: 'Z (fixed letter)' } : { status: 'bad', label: 'This position is always the letter Z' }));
  const check = seg('check', v, 14, 1, 'Check digit', (t) => {
    const expected = gstinCheckChar(v.slice(0, 14));
    return t === expected ? { status: 'ok', label: 'check digit OK' } : { status: 'bad', label: `check digit should be ${expected} - probably a typo` };
  });
  const segs = [state, pan, entity, z, check];
  if (v.length > 15) segs.push({ id: 'extra', text: v.slice(15), size: v.length - 15, status: 'bad', label: 'A GSTIN has exactly 15 characters', hint: '' });
  const allOk = v.length === 15 && segs.every((s) => s.status === 'ok');
  return { kind: 'gstin', value: v, segs, complete: v.length >= 15, allOk, summary: allOk ? `Well-formed GSTIN - ${STATE_CODES[v.slice(0, 2)]}, ${PAN_HOLDER_TYPES[v[5]]}` : null };
}

function parsePan(v: string): Parsed {
  const series = seg('series', v, 0, 3, 'PAN series, 3 letters', (t) =>
    !isLetters(t) ? { status: 'bad', label: 'A PAN starts with letters' } : t.length < 3 ? { status: 'partial', label: 'PAN series' } : { status: 'ok', label: `Series ${t}` });
  const holder = seg('holder', v, 3, 1, 'Holder type letter', (t) =>
    PAN_HOLDER_TYPES[t] ? { status: 'ok', label: `${t} - ${PAN_HOLDER_TYPES[t]}` } : { status: 'bad', label: `'${t}' is not a real PAN holder type` });
  const initial = seg('initial', v, 4, 1, 'Name initial', (t) => (isLetters(t) ? { status: 'ok', label: `Name initial ${t}` } : { status: 'bad', label: 'This must be a letter' }));
  const serial = seg('serial', v, 5, 4, 'Serial, 4 digits', (t) =>
    !isDigits(t) ? { status: 'bad', label: 'The next 4 characters are digits' } : t.length < 4 ? { status: 'partial', label: 'Serial number' } : { status: 'ok', label: `Serial ${t}` });
  const last = seg('last', v, 9, 1, 'Check letter', (t) => (isLetters(t) ? { status: 'ok', label: `Check letter ${t}` } : { status: 'bad', label: 'The last character is a letter' }));
  const segs = [series, holder, initial, serial, last];
  if (v.length > 10) segs.push({ id: 'extra', text: v.slice(10), size: v.length - 10, status: 'bad', label: 'A PAN has exactly 10 characters', hint: '' });
  const allOk = v.length === 10 && segs.every((s) => s.status === 'ok');
  return { kind: 'pan', value: v, segs, complete: v.length >= 10, allOk, summary: allOk ? `PAN ${v} - ${PAN_HOLDER_TYPES[v[3]]}` : null };
}

function parseUdyam(v: string): Parsed {
  const prefix = seg('prefix', v, 0, 5, 'UDYAM', (t) => ('UDYAM'.startsWith(t) ? (t.length === 5 ? { status: 'ok', label: 'UDYAM' } : { status: 'partial', label: 'UDYAM' }) : { status: 'bad', label: 'Starts with UDYAM' }));
  const state = seg('ustate', v, 5, 2, 'State, 2 letters', (t) => (!isLetters(t) ? { status: 'bad', label: 'State is 2 letters, e.g. GJ' } : t.length < 2 ? { status: 'partial', label: 'State' } : { status: 'ok', label: `State ${t}` }));
  const district = seg('district', v, 7, 2, 'District, 2 digits', (t) => (!isDigits(t) ? { status: 'bad', label: 'District is 2 digits' } : t.length < 2 ? { status: 'partial', label: 'District' } : { status: 'ok', label: `District ${t}` }));
  const serial = seg('userial', v, 9, 7, 'Serial, 7 digits', (t) => (!isDigits(t) ? { status: 'bad', label: 'The serial is 7 digits' } : t.length < 7 ? { status: 'partial', label: 'Serial number' } : { status: 'ok', label: `Serial ${t}` }));
  const segs = [prefix, state, district, serial];
  if (v.length > 16) segs.push({ id: 'extra', text: v.slice(16), size: v.length - 16, status: 'bad', label: 'Too many characters for a Udyam number', hint: '' });
  const allOk = v.length === 16 && segs.every((s) => s.status === 'ok');
  return { kind: 'udyam', value: v, segs, complete: v.length >= 16, allOk, summary: allOk ? `Well-formed Udyam number (${v.slice(5, 7)})` : null };
}

export function parseIdentifier(raw: string): Parsed {
  const v = clean(raw);
  const kind = detectKind(v);
  if (kind && kind !== 'gstin' && kind !== 'pan' && kind !== 'udyam') {
    return { kind, value: v, segs: [], complete: true, allOk: true, summary: `Looks like a ${kindLabel(kind)}. Its parts are decoded when you check it` };
  }
  if (kind === 'pan') return parsePan(v);
  if (kind === 'udyam') return parseUdyam(v);
  if (kind === 'gstin') return parseGstin(v);
  return { kind: null, value: v, segs: [], complete: false, allOk: false, summary: null };
}

/** Pretty form of a stored number. */
const KIND_LABEL: Record<string, string> = {
  gstin: 'GSTIN', pan: 'PAN', udyam: 'Udyam number', cin: 'CIN', llpin: 'LLPIN', tan: 'TAN', ifsc: 'IFSC', iec: 'IEC',
  fssai: 'FSSAI licence number', esic: 'ESIC employer code', pf: 'PF establishment code',
};
export const kindLabel = (k: Kind | string): string => KIND_LABEL[k] ?? 'GSTIN';

/** Numbers the GST registry can be asked about, or that are saved as a supplier column. Everything else is format-checked only. */
export const SAVEABLE_KINDS: readonly string[] = ['gstin', 'pan', 'udyam'];
