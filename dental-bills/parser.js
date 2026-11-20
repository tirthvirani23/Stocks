/* Turns what the doctor says into a bill:
 *   "Ramesh Patel, root canal, 3500, cash"
 *   "પેશન્ટ નું નામ રમેશ પટેલ, રૂટ કેનાલ, સાડા ત્રણ હજાર"
 * into { name, items:[{desc, amount}], mode }.
 * Works on English (Indian accent), Gujarati script and Gujarati spoken in English letters.
 */
(function (global) {
  'use strict';

  const GU = /[઀-૿]/;

  // ---------- Procedures (key "=" prefix = whole word only) ----------
  const PROCS = [
    ['Root Canal Treatment (RCT)', ['root canal treatment', 'root canal therapy', 'root canal', 'rct', 'r c t', 'root kenal', 'રૂટ કેનાલ', 'રુટ કેનાલ', 'રૂટ કેનલ', 'આરસીટી', 'આર સી ટી', 'આર.સી.ટી']],
    ['Re-RCT', ['re rct', 're root canal', 'retreatment', 'rerct']],
    ['Extraction', ['extraction', 'extract', 'extracted', 'tooth removal', 'tooth removed', 'removed tooth', 'dant kadhyo', 'daant kadhyo', 'dadh kadhi', 'એક્સ્ટ્રેક્શન', 'એક્સટ્રેક્શન', 'એકસ્ટ્રેક્શન', 'દાંત કાઢ', 'દાઢ કાઢ', 'દાંત કઢાવ', 'દાઢ કઢાવ', 'કાઢ્યો', 'કાઢ્યા', 'કાઢી', 'કઢાવ્યો', 'કઢાવી', 'કઢાવ્યા']],
    ['Surgical Extraction (Wisdom Tooth)', ['surgical extraction', 'wisdom tooth', 'wisdom teeth', 'impaction', 'impacted', 'akkal dadh', 'akal dadh', 'અક્કલ દાઢ', 'અકલ દાઢ', 'અક્કલદાઢ']],
    ['Scaling & Polishing', ['scaling and polishing', 'scaling', 'teeth cleaning', 'cleaning', 'polishing', 'safai', 'સફાઈ', 'સફાય', '=સાફ', 'ક્લીનિંગ', 'ક્લિનિંગ', 'સ્કેલિંગ', 'સ્કેલીંગ']],
    ['Filling', ['composite filling', 'cement filling', 'filling', 'composite', 'gic', 'light cure', 'ફિલિંગ', 'ફીલીંગ', 'ફિલીંગ', 'પુરાણ', 'પુરાવ', 'કમ્પોઝીટ']],
    ['Crown / Cap', ['crown', 'cap', 'કેપ', 'ક્રાઉન', '=ટોપી']],
    ['Zirconia Crown', ['zirconia crown', 'zirconia cap', 'zirconia', 'zirconium', 'ઝિર્કોનિયા', 'ઝીરકોનીયા', 'ઝિરકોનિયા']],
    ['Ceramic Crown (PFM)', ['ceramic crown', 'ceramic cap', 'porcelain crown', 'pfm', 'ceramic', 'સિરામિક', 'સેરામિક']],
    ['Metal Crown', ['metal crown', 'metal cap', 'મેટલ કેપ', 'મેટલ']],
    ['Bridge', ['bridge', 'fixed partial denture', 'fpd', 'બ્રિજ', 'બ્રીજ']],
    ['Complete Denture', ['complete denture', 'full denture', 'teeth set', 'full set', '=cd', 'batrisi', 'batrishi', 'battisi', 'chokthu', 'chokathu', 'chokdu', 'બત્રીસી', 'બત્રીશી', 'ચોકઠું', 'ચોકઠા', 'ચોકઠુ']],
    ['Partial Denture', ['removable partial denture', 'partial denture', 'rpd', 'પાર્શિયલ']],
    ['Denture', ['denture', 'ડેન્ચર', 'ડેંચર']],
    ['Denture Repair', ['denture repair', 'repair', 'રિપેર', 'રીપેર']],
    ['Implant', ['implant', 'ઇમ્પ્લાન્ટ', 'ઈમ્પ્લાન્ટ', 'ઇમ્પ્લાંટ', 'ઈમ્પ્લાંટ']],
    ['X-Ray', ['x ray', 'xray', 'rvg', 'opg', 'એક્સ રે', 'એક્સરે', 'એક્સ-રે']],
    ['Consultation', ['consultation', 'consulting', 'check up', 'checkup', 'examination', 'ચેકઅપ', 'ચેક અપ', 'તપાસ', 'કન્સલ્ટેશન']],
    ['Orthodontic Treatment (Braces)', ['orthodontic treatment', 'orthodontic', 'braces', 'brace', 'બ્રેસીસ', 'બ્રેસિસ', '=તાર']],
    ['Teeth Whitening', ['teeth whitening', 'whitening', 'bleaching', 'બ્લીચિંગ', 'વ્હાઇટનિંગ']],
    ['Post & Core', ['post and core', 'post core', 'પોસ્ટ']],
    ['Pulpectomy', ['pulpectomy', 'pulpotomy', 'પલ્પેક્ટોમી']],
    ['Gum Treatment (Flap Surgery)', ['flap surgery', 'gum surgery', 'gum treatment', 'flap', 'curettage', 'પેઢા', 'પેઢાં']],
    ['Veneer / Laminate', ['veneer', 'laminate', 'વિનિયર', 'લેમિનેટ']],
    ['Re-cementation', ['re cementation', 'recementation', 'cementation', 'cap fixing']],
    ['Night Guard', ['night guard', 'mouth guard']],
    ['Dressing', ['dressing', 'ડ્રેસિંગ']],
    ['Medicines', ['medicine', 'tablet', '=દવા', '=દવાઓ']],
  ];

  const PAY = [
    ['UPI', ['upi', 'gpay', 'google pay', 'phonepe', 'phone pe', 'paytm', 'online', 'qr', 'યુપીઆઈ', 'ઓનલાઇન', 'ઓનલાઈન', 'ગૂગલ પે', 'ફોન પે']],
    ['Card', ['card', 'debit card', 'credit card', 'કાર્ડ']],
    ['Cash', ['cash', 'rokda', 'rokad', 'રોકડા', 'રોકડ', 'કેશ']],
  ];

  const CURRENCY = new Set(['rs', 'rupees', 'rupee', 'rupaye', 'rupiya', 'rupiye', 'inr', 'રૂપિયા', 'રૂ', 'રૂપિયે', 'રુપિયા', '₹', 'amount', 'fees', 'fee', 'charge', 'charges', 'total', 'ફી', 'રકમ', 'paid', 'received', 'taken', 'લીધા', 'આપ્યા']);
  const TOOTH = new Set(['tooth', 'teeth', 'number', 'no', 'દાંત', 'દાઢ', 'નંબર']);

  const STOP = new Set(('patient patients name named naam is was the a an and of for mister procedure treatment done did do has have had been ' +
    'amount received receive paid pay taken take took fees fee charges charge total bill rs rupees rupee only with to ' +
    'please okay ok then also plus today date tooth teeth number no ka ki ke hai nu ne che chhe karyu lidha by on in at it ' +
    'his her my we so he she they this that sir madam mam ma\'am bhi aur ' +
    'નામ પેશન્ટ પેશંટ દર્દી દર્દીનું નું ના ની ને નો છે હતું કર્યું કરી કર્યો કરાવ્યું કરાવ્યો લીધા લીધી લીધું આપ્યા અને માટે ' +
    'ફી રકમ ટ્રીટમેન્ટ સારવાર પ્રોસિજર બિલ તારીખ આજે નંબર ભરેલા ભર્યા ચૂકવ્યા').split(/\s+/));

  // ---------- Numbers ----------
  const WORDS = {
    zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
    eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19,
    twenty: 20, thirty: 30, forty: 40, fourty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90,
    dhai: 2.5, adhai: 2.5, dedh: 1.5, dodh: 1.5,
    'એક': 1, 'બે': 2, 'ત્રણ': 3, 'ચાર': 4, 'પાંચ': 5, 'છ': 6, 'સાત': 7, 'આઠ': 8, 'નવ': 9, 'દસ': 10, 'દશ': 10,
    'અગિયાર': 11, 'અગીયાર': 11, 'બાર': 12, 'તેર': 13, 'ચૌદ': 14, 'પંદર': 15, 'સોળ': 16, 'સત્તર': 17, 'અઢાર': 18, 'ઓગણીસ': 19,
    'વીસ': 20, 'એકવીસ': 21, 'બાવીસ': 22, 'ત્રેવીસ': 23, 'ચોવીસ': 24, 'પચીસ': 25, 'પચ્ચીસ': 25, 'છવ્વીસ': 26, 'સત્તાવીસ': 27,
    'અઠ્ઠાવીસ': 28, 'ઓગણત્રીસ': 29, 'ત્રીસ': 30, 'પાંત્રીસ': 35, 'ચાલીસ': 40, 'ચાળીસ': 40, 'પિસ્તાલીસ': 45, 'પચાસ': 50,
    'પંચાવન': 55, 'સાઠ': 60, 'પાંસઠ': 65, 'સિત્તેર': 70, 'પંચોતેર': 75, 'એંસી': 80, 'એંશી': 80, 'પંચ્યાસી': 85, 'નેવું': 90,
    'પંચાણું': 95, 'અઢી': 2.5, 'દોઢ': 1.5,
  };
  const MULTS = { hundred: 100, thousand: 1000, lakh: 100000, lakhs: 100000, lac: 100000, sau: 100, so: 100, hazar: 1000, hajar: 1000, hazaar: 1000, hajaar: 1000, 'સો': 100, 'હજાર': 1000, 'લાખ': 100000 };
  const MODS = { sada: 0.5, sade: 0.5, sadhe: 0.5, saade: 0.5, saadhe: 0.5, sava: 0.25, savva: 0.25, pona: -0.25, 'સાડા': 0.5, 'સવા': 0.25, 'પોણા': -0.25 };

  function classify(tok) {
    let m = tok.match(/^(\d+(?:\.\d+)?)(k)?$/);
    if (m) return { kind: 'digit', v: parseFloat(m[1]) * (m[2] ? 1000 : 1) };
    if (tok in WORDS) return { kind: 'word', v: WORDS[tok] };
    if (tok in MULTS) return { kind: 'mult', v: MULTS[tok] };
    if (tok in MODS) return { kind: 'mod', v: MODS[tok] };
    // Gujarati compounds like પંદરસો (1500), ત્રણહજાર (3000)
    for (const suf of ['સો', 'હજાર']) {
      if (tok.length > suf.length && tok.endsWith(suf)) {
        const head = tok.slice(0, -suf.length);
        if (head in WORDS) return { kind: 'compound', v: WORDS[head] * MULTS[suf], mult: MULTS[suf] };
      }
    }
    return null;
  }

  function findNumbers(tokens) {
    const out = [];
    let g = null;
    const close = () => {
      if (g && g.has) out.push({ start: g.start, end: g.end, value: Math.round(g.total + g.cur) });
      g = null;
    };
    const open = (i) => { g = { start: i, end: i, total: 0, cur: 0, has: false, last: null, lastMult: 0, mod: 0 }; };
    for (let i = 0; i < tokens.length; i++) {
      const c = classify(tokens[i]);
      if (!c) {
        if (g && tokens[i] === 'and' && i + 1 < tokens.length && classify(tokens[i + 1])) continue;
        close();
        continue;
      }
      if (c.kind === 'mod') { close(); open(i); g.mod = c.v; continue; }
      if (!g) open(i);
      if (c.kind === 'digit' || c.kind === 'word') {
        let ok = !g.has ||
          (g.last === 'mult' && (c.v < g.lastMult)) ||
          (g.last === 'word' && c.kind === 'word' && g.cur >= 20 && g.cur % 10 === 0 && c.v < 10);
        if (!ok) { close(); open(i); }
        g.cur += c.v + g.mod; g.mod = 0; g.has = true; g.last = c.kind; g.end = i;
      } else if (c.kind === 'mult') {
        if (g.has && g.last === 'mult' && c.v <= g.lastMult) { close(); open(i); }
        if (g.mod) { g.cur = 1 + g.mod; g.mod = 0; }
        if (c.v === 100) { g.cur = (g.cur || 1) * 100; }
        else { g.total += (g.cur || 1) * c.v; g.cur = 0; }
        g.has = true; g.last = 'mult'; g.lastMult = c.v; g.end = i;
      } else if (c.kind === 'compound') {
        if (g.has) { close(); open(i); }
        if (c.mult === 100) g.cur = c.v; else { g.total += c.v; g.cur = 0; }
        g.has = true; g.last = 'mult'; g.lastMult = c.mult; g.end = i;
      }
    }
    close();
    return out;
  }

  // ---------- Text helpers ----------
  const GU_DIGITS = '૦૧૨૩૪૫૬૭૮૯';
  function normalize(text) {
    let t = String(text || '').toLowerCase();
    t = t.replace(/[૦-૯]/g, (d) => String(GU_DIGITS.indexOf(d)));
    t = t.replace(/₹\s*/g, ' rs ');
    t = t.replace(/(\d),(?=\d)/g, '$1');
    t = t.replace(/\brs\.?(?=\d)/g, 'rs ');
    t = t.replace(/(\d)(?=[a-z઀-૿])(?!k\b)/g, '$1 ');
    t = t.replace(/([a-z઀-૿])(?=\d)/g, '$1 ');
    t = t.replace(/(\d)\.(?!\d)/g, '$1 ');
    t = t.replace(/[^\w઀-૿.\s]|_/g, ' ');
    t = t.replace(/(^|\s)\.|\.(?=\s|$)/g, ' ');
    t = t.replace(/([a-z])\.(?=[a-z])/g, '$1 ');
    return t.split(/\s+/).filter(Boolean);
  }

  function tokMatch(key, tok) {
    if (GU.test(key)) return tok === key || tok.startsWith(key);
    return tok === key || tok === key + 's' || tok === key + 'es';
  }

  function buildMatcher(list) {
    const entries = [];
    for (const [name, keys] of list) {
      for (let k of keys) {
        let exact = false;
        if (k[0] === '=') { exact = true; k = k.slice(1); }
        const toks = normalize(k);
        entries.push({ name, toks, exact, len: toks.join(' ').length });
      }
    }
    entries.sort((a, b) => b.toks.length - a.toks.length || b.len - a.len);
    return function (tokens, i) {
      for (const e of entries) {
        if (i + e.toks.length > tokens.length) continue;
        let ok = true;
        for (let j = 0; j < e.toks.length; j++) {
          const tk = tokens[i + j];
          if (e.exact ? tk !== e.toks[j] : !tokMatch(e.toks[j], tk)) { ok = false; break; }
        }
        if (ok) return { name: e.name, n: e.toks.length };
      }
      return null;
    };
  }
  const matchProc = buildMatcher(PROCS);
  const matchPay = buildMatcher(PAY);

  // ---------- Gujarati → English letters (for names on the PDF) ----------
  const CONS = { 'ક': 'k', 'ખ': 'kh', 'ગ': 'g', 'ઘ': 'gh', 'ઙ': 'n', 'ચ': 'ch', 'છ': 'chh', 'જ': 'j', 'ઝ': 'jh', 'ઞ': 'n', 'ટ': 't', 'ઠ': 'th', 'ડ': 'd', 'ઢ': 'dh', 'ણ': 'n', 'ત': 't', 'થ': 'th', 'દ': 'd', 'ધ': 'dh', 'ન': 'n', 'પ': 'p', 'ફ': 'f', 'બ': 'b', 'ભ': 'bh', 'મ': 'm', 'ય': 'y', 'ર': 'r', 'લ': 'l', 'વ': 'v', 'શ': 'sh', 'ષ': 'sh', 'સ': 's', 'હ': 'h', 'ળ': 'l' };
  const VOW = { 'અ': 'a', 'આ': 'a', 'ઇ': 'i', 'ઈ': 'i', 'ઉ': 'u', 'ઊ': 'u', 'ઋ': 'ru', 'એ': 'e', 'ઐ': 'ai', 'ઓ': 'o', 'ઔ': 'au', 'ઍ': 'e', 'ઑ': 'o' };
  const MATRA = { 'ા': 'a', 'િ': 'i', 'ી': 'i', 'ુ': 'u', 'ૂ': 'u', 'ૃ': 'ru', 'ે': 'e', 'ૈ': 'ai', 'ો': 'o', 'ૌ': 'au', 'ૅ': 'e', 'ૉ': 'o' };
  const VIRAMA = '્';

  function translitWord(w) {
    // syllables: {c: consonant latin or '', v: vowel latin, schwa: bool, conj: bool}
    const syl = [];
    const chars = Array.from(w);
    for (let i = 0; i < chars.length; i++) {
      const ch = chars[i];
      if (CONS[ch] !== undefined) {
        const s = { c: CONS[ch], v: 'a', schwa: true, conj: false };
        const nx = chars[i + 1];
        if (nx === VIRAMA) { s.v = ''; s.schwa = false; s.conj = true; i++; }
        else if (nx === '઼') { i++; }
        else if (MATRA[nx] !== undefined) { s.v = MATRA[nx]; s.schwa = false; i++; }
        syl.push(s);
      } else if (VOW[ch] !== undefined) {
        syl.push({ c: '', v: VOW[ch], schwa: false, conj: false });
      } else if (ch === 'ં' || ch === 'ઁ') {
        if (syl.length) syl[syl.length - 1].v += 'n';
      } else if (ch === 'ઃ') {
        if (syl.length) syl[syl.length - 1].v += 'h';
      } else if (/[a-z0-9]/i.test(ch)) {
        syl.push({ c: ch, v: '', schwa: false, conj: false });
      }
    }
    // final schwa is silent unless after a conjunct (e.g. નરેન્દ્ર → Narendra) or the word is one letter
    const last = syl[syl.length - 1];
    if (last && last.schwa && syl.length > 1 && !syl[syl.length - 2].conj) last.v = '';
    // medial schwa deletion: V C(a) C V(full) → drop
    for (let i = 1; i < syl.length - 1; i++) {
      const s = syl[i], p = syl[i - 1], n = syl[i + 1];
      if (s.schwa && s.v === 'a' && p.v && !p.conj && n.c && !n.schwa && n.v) s.v = '';
    }
    return syl.map((s) => s.c + s.v).join('');
  }

  function titleCase(s) {
    return s.split(/\s+/).filter(Boolean).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  }

  function toEnglish(s) {
    if (!s) return '';
    if (!GU.test(s)) return s;
    return s.split(/(\s+)/).map((p) => (GU.test(p) ? titleCase(translitWord(p)) : p)).join('');
  }

  // ---------- Spoken date ----------
  const MONTHS = {
    january: 1, jan: 1, february: 2, feb: 2, march: 3, mar: 3, april: 4, apr: 4, may: 5, june: 6, jun: 6, july: 7, jul: 7,
    august: 8, aug: 8, september: 9, sept: 9, sep: 9, october: 10, oct: 10, november: 11, nov: 11, december: 12, dec: 12,
    'જાન્યુઆરી': 1, 'જાન્યુઆરિ': 1, 'ફેબ્રુઆરી': 2, 'ફેબ્રુઆરિ': 2, 'માર્ચ': 3, 'એપ્રિલ': 4, 'મે': 5, 'જૂન': 6, 'જુન': 6,
    'જુલાઈ': 7, 'જુલાઇ': 7, 'ઓગસ્ટ': 8, 'ઑગસ્ટ': 8, 'ઓગષ્ટ': 8, 'સપ્ટેમ્બર': 9, 'સપ્ટેમ્બર': 9, 'ઓક્ટોબર': 10, 'ઑક્ટોબર': 10,
    'નવેમ્બર': 11, 'નવેમ્બર': 11, 'ડિસેમ્બર': 12, 'ડીસેમ્બર': 12,
  };
  const ORD = new Set(['st', 'nd', 'rd', 'th', 'મી', 'ની', 'એ']);
  const DATEWORD = new Set(['date', 'dated', 'tarikh', 'tarik', 'tareekh', 'તારીખ', 'તા']);
  const TODAY = new Set(['today', 'aaje', 'aaj', 'આજે', 'આજ', 'આજની']);
  const YEST = new Set(['yesterday', 'ગઈકાલે', 'ગઇકાલે', 'ગઈ', 'ગઇ', 'gai', 'gaikale', 'kale']);

  function iso(y, m, d) {
    const dt = new Date(y, m - 1, d);
    if (dt.getFullYear() !== y || dt.getMonth() !== m - 1 || dt.getDate() !== d) return '';
    return y + '-' + String(m).padStart(2, '0') + '-' + String(d).padStart(2, '0');
  }
  function fullYear(y, now) {
    if (y == null) return null;
    y = Number(y);
    if (y < 100) y += 2000;
    return y >= 2000 && y <= now.getFullYear() + 1 ? y : null;
  }
  function withYear(d, m, y, now) {
    if (y) return iso(y, m, d);
    let out = iso(now.getFullYear(), m, d);
    // a date said in January for "28 December" means last year
    if (out && new Date(now.getFullYear(), m - 1, d) - now > 2 * 86400000) out = iso(now.getFullYear() - 1, m, d);
    return out;
  }
  function shift(now, days) { const d = new Date(now); d.setDate(d.getDate() + days); return iso(d.getFullYear(), d.getMonth() + 1, d.getDate()); }

  // numeric dates like 20/11/2026 or 20-11 must be pulled out before punctuation is removed
  function pullNumericDate(text, now) {
    let t = String(text || '').replace(/[૦-૯]/g, (d) => String('૦૧૨૩૪૫૬૭૮૯'.indexOf(d)));
    let found = '';
    t = t.replace(/(^|[^\d.])(\d{1,2})\s*([\/-])\s*(\d{1,2})(?:\s*\3\s*(\d{2,4}))?(?![\d.])/, (all, pre, d, sep, m, y) => {
      const yy = fullYear(y, now);
      const r = withYear(Number(d), Number(m), y ? yy : null, now);
      if (!r || (y && !yy)) return all;
      found = r; return pre + ' ';
    });
    if (!found) {
      t = t.replace(/(^|[^\d.])(\d{1,2})\.(\d{1,2})\.(\d{2,4})(?![\d.])/, (all, pre, d, m, y) => {
        const yy = fullYear(y, now); const r = yy && withYear(Number(d), Number(m), yy, now);
        if (!r) return all; found = r; return pre + ' ';
      });
    }
    return { text: t, date: found };
  }

  function findDate(tokens, used, now) {
    const num = (i) => (i >= 0 && i < tokens.length && !used[i] && /^\d{1,4}$/.test(tokens[i]) ? Number(tokens[i]) : null);
    const mark = (...idx) => idx.forEach((i) => { if (i >= 0 && i < tokens.length) used[i] = true; });
    for (let i = 0; i < tokens.length; i++) {
      const m = MONTHS[tokens[i]];
      if (!m) continue;
      // day before month: "20 november", "20th november", "20 મી નવેમ્બર"
      let di = i - 1; if (di >= 0 && ORD.has(tokens[di])) di--;
      let d = num(di);
      let yi = i + 1, y = num(yi);
      if (d == null || d < 1 || d > 31) {
        // month before day: "november 20", "november 20th 2026"
        di = i + 1; d = num(di);
        if (d == null || d < 1 || d > 31) continue;
        yi = di + 1; if (yi < tokens.length && ORD.has(tokens[yi])) { mark(yi); yi++; }
        y = num(yi);
      } else if (tokens[i - 1] !== String(d)) mark(i - 1);
      const yy = y != null && y >= 2000 ? fullYear(y, now) : (y != null && y < 100 && y >= 20 ? fullYear(y, now) : null);
      const r = withYear(d, m, yy, now);
      if (!r) continue;
      mark(i, di); if (yy) mark(yi);
      if (DATEWORD.has(tokens[di - 1])) mark(di - 1);
      return r;
    }
    for (let i = 0; i < tokens.length; i++) {
      if (TODAY.has(tokens[i])) { mark(i); return shift(now, 0); }
      if (YEST.has(tokens[i]) && (tokens[i] !== 'gai' || tokens[i + 1] === 'kale') && (tokens[i] !== 'ગઈ' && tokens[i] !== 'ગઇ' || /^કાલ/.test(tokens[i + 1] || ''))) {
        mark(i); if (/^(kale|કાલે|કાલ)$/.test(tokens[i + 1] || '')) mark(i + 1); return shift(now, -1);
      }
      if (DATEWORD.has(tokens[i])) {
        let j = i + 1; const d = num(j);
        if (d == null || d < 1 || d > 31) continue;
        mark(i, j); if (ORD.has(tokens[j + 1])) mark(j + 1);
        let r = withYear(d, now.getMonth() + 1, null, now);
        if (r && new Date(r) > now) { const pm = new Date(now.getFullYear(), now.getMonth() - 1, 1); r = iso(pm.getFullYear(), pm.getMonth() + 1, d); }
        return r || '';
      }
    }
    return '';
  }

  // ---------- Main parse ----------
  function parse(text, now) {
    now = now || new Date();
    const pre = pullNumericDate(text, now);
    const tokens = normalize(pre.text);
    const used = new Array(tokens.length).fill(false);
    const marks = []; // {pos, type, ...}
    const date = pre.date || findDate(tokens, used, now);
    tokens.forEach((t, i) => { if (ORD.has(t) && i > 0 && /^\d/.test(tokens[i - 1]) && used[i - 1]) used[i] = true; });

    for (let i = 0; i < tokens.length;) {
      if (used[i]) { i++; continue; }
      const m = matchProc(tokens, i);
      if (m) { marks.push({ pos: i, type: 'proc', name: m.name }); for (let j = 0; j < m.n; j++) used[i + j] = true; i += m.n; continue; }
      i++;
    }
    let mode = '';
    for (let i = 0; i < tokens.length;) {
      if (used[i]) { i++; continue; }
      const m = matchPay(tokens, i);
      if (m) { mode = mode || m.name; for (let j = 0; j < m.n; j++) used[i + j] = true; i += m.n; continue; }
      i++;
    }
    const nums = findNumbers(tokens);
    for (const n of nums) {
      let overlap = false;
      for (let j = n.start; j <= n.end; j++) if (used[j]) overlap = true;
      if (overlap) continue;
      const prev = tokens[n.start - 1], prev2 = tokens[n.start - 2], next = tokens[n.end + 1];
      const currency = CURRENCY.has(prev) || CURRENCY.has(next) || CURRENCY.has(prev2);
      const tooth = (TOOTH.has(prev) || TOOTH.has(prev2)) && !currency && n.value >= 11 && n.value <= 85;
      for (let j = n.start; j <= n.end; j++) used[j] = true;
      if (tooth) marks.push({ pos: n.start, type: 'tooth', value: n.value });
      else if (n.value >= 50 || (currency && n.value > 0)) marks.push({ pos: n.start, type: 'amt', value: n.value });
    }
    tokens.forEach((t, i) => { if (CURRENCY.has(t) || TOOTH.has(t)) used[i] = true; });
    marks.sort((a, b) => a.pos - b.pos);

    // Build bill lines
    const items = [];
    let pending = [], pendingAmt = null;
    for (const mk of marks) {
      if (mk.type === 'proc') {
        if (pendingAmt !== null) { items.push({ desc: mk.name, amount: pendingAmt, pos: mk.pos }); pendingAmt = null; }
        else if (!pending.includes(mk.name)) pending.push(mk.name);
      } else if (mk.type === 'amt') {
        if (pending.length) { items.push({ desc: pending.join(' + '), amount: mk.value, pos: mk.pos }); pending = []; }
        else if (items.length && pendingAmt === null && !items[items.length - 1].amount) items[items.length - 1].amount = mk.value;
        else if (pendingAmt === null) pendingAmt = mk.value;
        else pendingAmt += mk.value;
      }
    }
    if (pending.length) items.push({ desc: pending.join(' + '), amount: pendingAmt || 0, pos: Infinity });
    else if (pendingAmt !== null) items.push({ desc: 'Dental Treatment', amount: pendingAmt, pos: Infinity });

    // Tooth numbers → attach to nearest line
    for (const mk of marks.filter((m) => m.type === 'tooth')) {
      if (!items.length) continue;
      let best = items[0];
      for (const it of items) if (Math.abs(it.pos - mk.pos) < Math.abs(best.pos - mk.pos)) best = it;
      best.teeth = (best.teeth || []).concat(mk.value);
    }
    items.forEach((it) => { if (it.teeth) it.desc += ' - Tooth ' + it.teeth.join(', '); delete it.teeth; delete it.pos; });

    // Name = first run of leftover words before the first procedure / amount
    const firstMark = marks.length ? marks[0].pos : tokens.length;
    const runs = [];
    let run = [];
    tokens.forEach((t, i) => {
      if (!used[i] && !STOP.has(t) && !/^\d/.test(t) && t.length > 0) run.push(i);
      else if (run.length) { runs.push(run); run = []; }
    });
    if (run.length) runs.push(run);
    let pick = runs.find((r) => r[0] < firstMark);
    if (!pick && runs.length) pick = runs.slice().sort((a, b) => b.length - a.length)[0];
    let name = pick ? pick.slice(0, 4).map((i) => tokens[i]).join(' ') : '';
    name = titleCase(toEnglish(name));

    return { name, date, items, mode, total: items.reduce((s, it) => s + (Number(it.amount) || 0), 0) };
  }

  function score(r) {
    return (r.name ? 2 : 0) + (r.items.length ? 2 : 0) + (r.items.some((i) => i.amount > 0) ? 2 : 0) +
      (r.items.some((i) => i.desc !== 'Dental Treatment') ? 1 : 0) + (r.date ? 2 : 0);
  }

  function best(candidates, now) {
    let top = null, topScore = -1;
    for (const c of candidates) {
      const r = parse(c, now);
      const s = score(r);
      if (s > topScore) { top = Object.assign(r, { heard: c }); topScore = s; }
    }
    return top;
  }

  // ---------- Amount in words (Indian system) ----------
  const ONES = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'];
  const TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];
  function two(n) { return n < 20 ? ONES[n] : TENS[Math.floor(n / 10)] + (n % 10 ? ' ' + ONES[n % 10] : ''); }
  function inWords(num) {
    num = Math.round(Number(num) || 0);
    if (num === 0) return 'Zero';
    const parts = [];
    const crore = Math.floor(num / 10000000); num %= 10000000;
    const lakh = Math.floor(num / 100000); num %= 100000;
    const thou = Math.floor(num / 1000); num %= 1000;
    const hund = Math.floor(num / 100); num %= 100;
    if (crore) parts.push(inWords(crore) + ' Crore');
    if (lakh) parts.push(two(lakh) + ' Lakh');
    if (thou) parts.push(two(thou) + ' Thousand');
    if (hund) parts.push(ONES[hund] + ' Hundred');
    if (num) parts.push(two(num));
    return parts.join(' ');
  }

  global.BillParser = { parse, best, toEnglish, inWords, PROCEDURES: PROCS.map((p) => p[0]) };
})(typeof window !== 'undefined' ? window : globalThis);
