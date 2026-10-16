/* AbdulmajeedPharma (APH) — Cloud layer for the web app
   © Dr. Abdulmajeed Abdullah Almakhedhi — WhatsApp 781733795 • 7a8b1d@gmail.com
   يضيف: ذكاء اصطناعي حقيقي (Gemini / OpenAI)، التعرف على الدواء من صورته،
   مزامنة القاعدة من موقع التحكم، ونتائج بحث مقسّمة (دواء ← شركات ← وكيل ودولة).
   يعمل دون إنترنت: كل دالة ترجع تلقائياً للوضع المحلي عند الفشل. */
(function () {
  'use strict';
  const K = {
    provider: 'aph_ai_provider', gemini: 'aph_gemini_key', openai: 'aph_openai_key',
    gmodel: 'aph_gemini_model', omodel: 'aph_openai_model', url: 'aph_sync_url',
    last: 'aph_last_sync',
  };
  const DEFAULT_URL = 'https://raw.githubusercontent.com/Abd800d/PharmaAbud/main/webapp/aph-database.json';
  const get = (k, d) => localStorage.getItem(k) || d;
  const set = (k, v) => localStorage.setItem(k, v);

  const APH = {
    get provider() { return get(K.provider, 'auto'); },
    get geminiKey() { return (get(K.gemini, '') || '').trim(); },
    get openaiKey() { return (get(K.openai, '') || '').trim(); },
    get geminiModel() { return get(K.gmodel, 'gemini-2.5-flash'); },
    get openaiModel() { return get(K.omodel, 'gpt-4o-mini'); },
    get syncUrl() { return get(K.url, DEFAULT_URL); },
    hasKey() { return !!(APH.geminiKey || APH.openaiKey); },
    active() {
      const p = APH.provider;
      if (p === 'offline') return 'offline';
      if (p === 'gemini' || p === 'openai') return p;
      return APH.geminiKey ? 'gemini' : (APH.openaiKey ? 'openai' : 'offline');
    },
  };
  window.APH = APH;

  const SYSTEM = 'You are the APH Drug Assistant, a reference clinical pharmacist inside AbdulmajeedPharma (APH) '
    + 'by Dr. Abdulmajeed Abdullah Almakhedhi, serving pharmacists and physicians in Yemen and the Arab world. '
    + 'Rules: (1) Rely FIRST on the APH DATABASE context given with the question (generics, trade products, strengths, '
    + 'dosage forms, manufacturers, countries, Yemen agents). (2) If not in the context, use your pharmacology knowledge and say it is not from the APH database. '
    + '(3) NEVER invent a Yemeni agent or manufacturer - write "needs verification by APH admin". '
    + '(4) Answer in the language of the question, structured and concise: indication, usual adult dose, key interactions, warnings, pregnancy, alternatives/equivalent trade products. '
    + '(5) For high-risk drugs (warfarin, insulin, methotrexate, digoxin, lithium, opioids, oncology) stress lab monitoring and that the decision belongs to the treating physician. '
    + '(6) End with an official verification source (DailyMed / openFDA / WHO / BNF) and: "Educational information - not a substitute for medical advice." '
    + '(7) Provide reference drug information only; never diagnose a specific patient.';

  function clip(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n) + '…' : s; }

  // --------- context from the local APH database (RAG) ---------
  APH.context = function (q) {
    try {
      const hits = (typeof searchDrugs === 'function' ? searchDrugs(q) : []).slice(0, 3);
      if (!hits.length) return '';
      let out = 'APH DATABASE (local, curated):\n';
      hits.forEach(h => {
        const d = h.d;
        out += `- ${d.genericEn} / ${d.genericAr || ''} | system: ${d.systemEn} | group: ${d.subgroupEn} | ATC: ${d.atc || '-'}\n`;
        if (d.indications) out += '  indications: ' + clip(d.indications, 300) + '\n';
        if (d.dosage) out += '  dose: ' + clip(d.dosage, 300) + '\n';
        if (d.interactions) out += '  interactions: ' + clip(d.interactions, 300) + '\n';
        if (d.warnings) out += '  warnings: ' + clip(d.warnings, 300) + '\n';
        if (d.pregnancy) out += '  pregnancy: ' + clip(d.pregnancy, 150) + '\n';
        (d.products || []).slice(0, 8).forEach(p => {
          out += `   * ${p.brand} ${p.strength || ''} ${p.form || ''} - ${p.manufacturer || '?'} (${p.country || '?'})`
            + ` - Yemen agent: ${p.agentYemen || '-'}${p.verified ? ' [verified]' : ' [unverified]'}\n`;
        });
      });
      return out;
    } catch (e) { return ''; }
  };

  async function callGemini(prompt, dataUrl) {
    if (!APH.geminiKey) throw new Error('no Gemini key');
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${APH.geminiModel}:generateContent?key=${encodeURIComponent(APH.geminiKey)}`;
    const parts = [{ text: prompt }];
    if (dataUrl) {
      const i = dataUrl.indexOf(',');
      parts.unshift({ inline_data: { mime_type: dataUrl.slice(5, i).replace('data:', ''), data: dataUrl.slice(i + 1) } });
    }
    const res = await fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: SYSTEM }] },
        contents: [{ role: 'user', parts }],
        generationConfig: { temperature: 0.2, maxOutputTokens: 1400 },
      }),
    });
    const j = await res.json();
    if (!res.ok) throw new Error(`Gemini HTTP ${res.status}: ${clip(j.error && j.error.message || JSON.stringify(j), 180)}`);
    const c = (j.candidates || [])[0];
    const txt = ((c && c.content && c.content.parts) || []).map(p => p.text || '').join('').trim();
    if (!txt) throw new Error('Gemini returned an empty answer');
    return { text: txt, provider: 'gemini' };
  }

  async function callOpenAI(prompt, dataUrl) {
    if (!APH.openaiKey) throw new Error('no OpenAI key');
    const content = dataUrl
      ? [{ type: 'text', text: prompt }, { type: 'image_url', image_url: { url: dataUrl } }]
      : prompt;
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + APH.openaiKey },
      body: JSON.stringify({ model: APH.openaiModel, temperature: 0.2, max_tokens: 1400, messages: [{ role: 'system', content: SYSTEM }, { role: 'user', content }] }),
    });
    const j = await res.json();
    if (!res.ok) throw new Error(`OpenAI HTTP ${res.status}: ${clip(j.error && j.error.message || JSON.stringify(j), 180)}`);
    const txt = ((j.choices || [])[0] || {}).message;
    if (!txt || !txt.content) throw new Error('OpenAI returned an empty answer');
    return { text: String(txt.content).trim(), provider: 'openai' };
  }

  async function cloud(prompt, dataUrl) {
    const p = APH.active();
    if (p === 'offline') throw new Error('offline mode');
    const order = p === 'openai' ? [callOpenAI, callGemini] : [callGemini, callOpenAI];
    let lastErr = null;
    for (const fn of order) { try { return await fn(prompt, dataUrl); } catch (e) { lastErr = e; } }
    throw lastErr || new Error('AI unavailable');
  }

  // --------- chat: cloud first, local database fallback ---------
  window.askAI = async function () {
    const box = $('aiQ');
    const q = (box.value || '').trim();
    if (!q) return;
    bubble(q, true);
    box.value = '';
    const thinking = document.createElement('div');
    thinking.className = 'bubble bot';
    thinking.textContent = APH.active() === 'offline' ? '…' : '☁ …';
    $('chatLog').appendChild(thinking);
    thinking.scrollIntoView({ behavior: 'smooth' });
    let answer, tag;
    try {
      const ctx = APH.context(q);
      const r = await cloud(ctx ? ctx + '\n\nQUESTION / السؤال:\n' + q : q, null);
      answer = r.text;
      tag = r.provider === 'gemini' ? '☁ Gemini (Google AI)' : '☁ OpenAI GPT';
    } catch (e) {
      answer = (typeof aiAnswer === 'function' ? aiAnswer(q) : String(e.message))
        + (APH.active() === 'offline' ? '' : `\n\n⚠️ ${L('تعذر الاتصال بالذكاء السحابي — هذه الإجابة من قاعدة APH المحلية.', 'Cloud AI failed - this answer is from the local APH database.')}\n${e.message}`);
      tag = '📴 ' + L('قاعدة APH المحلية', 'Local APH database');
    }
    thinking.remove();
    bubble(tag + '\n\n' + answer, false);
  };

  // --------- identify a medicine from a photo ---------
  window.aiIdentify = async function (inp) {
    const f = inp && inp.files && inp.files[0];
    if (inp) inp.value = '';
    if (!f) return;
    if (!APH.hasKey()) {
      alert(L('أضف مفتاح Gemini أو OpenAI أولاً من «الإعدادات الذكية» في صفحة المزيد.',
        'Add a Gemini or OpenAI key first from "AI settings" on the More page.'));
      window.open('https://lens.google.com', '_blank');
      return;
    }
    go('ai');
    bubble(L('📷 صورة علبة دواء', '📷 Photo of a medicine pack'), true);
    const thinking = document.createElement('div');
    thinking.className = 'bubble bot';
    thinking.textContent = '☁ …';
    $('chatLog').appendChild(thinking);
    try {
      const dataUrl = await new Promise((ok, no) => {
        const r = new FileReader();
        r.onload = () => ok(r.result);
        r.onerror = no;
        r.readAsDataURL(f);
      });
      const prompt = L(
        'تعرّف على هذا الدواء من الصورة. اقرأ كل نص ظاهر: الاسم التجاري، الاسم العلمي، القوة، الشكل الصيدلاني، الشركة والدولة. ثم أجب بالترتيب: 1) الاسم التجاري 2) الاسم العلمي 3) القوة والشكل 4) الشركة والدولة 5) أهم دواعي الاستعمال 6) الجرعة المعتادة للبالغين 7) تحذيران مهمان 8) البدائل. إن لم تكن الصورة دواء فقل ذلك. واختم بـ: تحقق رسمياً عبر DailyMed / openFDA.',
        'Identify this medicine from the photo. Read every visible text: brand, generic (INN), strength, dosage form, manufacturer, country. Then answer in order: 1) brand 2) generic 3) strength & form 4) manufacturer & country 5) main indication 6) usual adult dose 7) two important warnings 8) alternatives. If it is not a medicine, say so. End with: verify via DailyMed / openFDA.');
      const r = await cloud(prompt, dataUrl);
      thinking.remove();
      let extra = '';
      const low = r.text.toLowerCase();
      const found = (window.DB && DB.drugs || []).find(d => d.genericEn && d.genericEn.length > 3 && low.includes(d.genericEn.toLowerCase()));
      if (found) extra = `\n\n✅ ${L('موجود في قاعدة APH', 'Found in the APH database')}: ${found.genericEn}`;
      bubble((r.provider === 'gemini' ? '☁ Gemini vision' : '☁ OpenAI vision') + '\n\n' + r.text + extra, false);
      if (found) {
        bubble(L('👇 اضغط لفتح ملف الدواء الكامل مع المنتجات ووكلاء اليمن', '👇 Tap to open the full drug file with products and Yemen agents'), false);
        const el = $('chatLog').lastElementChild;
        el.style.cursor = 'pointer';
        el.onclick = () => openDrug(found.id);
      }
    } catch (e) {
      thinking.remove();
      bubble('⚠️ ' + e.message + '\n' + L('يمكنك البحث بالصورة في Google Lens.', 'You can still search this photo with Google Lens.'), false);
    }
  };

  // --------- sync the published database from the control site ---------
  APH.sync = async function () {
    if (!navigator.onLine) { alert(L('لا يوجد إنترنت.', 'No internet connection.')); return; }
    const urls = [APH.syncUrl];
    if (!APH.syncUrl.includes('jsdelivr')) urls.push('https://cdn.jsdelivr.net/gh/Abd800d/PharmaAbud@main/webapp/aph-database.json');
    let data = null, used = '', err = '';
    for (const u of urls) {
      try {
        const r = await fetch(u, { cache: 'no-store' });
        if (!r.ok) { err = 'HTTP ' + r.status; continue; }
        const j = await r.json();
        if (j && Array.isArray(j.drugs)) { data = j; used = u; break; }
        err = L('الملف ليس قاعدة APH', 'Not an APH database');
      } catch (e) { err = e.message; }
    }
    if (!data) { alert(L('تعذر تنزيل القاعدة المنشورة: ', 'Could not download the published database: ') + err); return; }
    const byName = {};
    DB.drugs.forEach(d => { byName[norm(d.genericEn)] = d; });
    let nextId = Math.max(0, ...DB.drugs.map(d => d.id)) + 1;
    let added = 0, updated = 0, newP = 0, upP = 0, ann = 0;
    data.drugs.forEach(r => {
      const name = (r.genericEn || '').trim();
      if (!name) return;
      const key = norm(name);
      let d = byName[key];
      if (!d) {
        d = { id: nextId++, genericEn: name, products: [], source: 'APH control site' };
        DB.drugs.push(d);
        byName[key] = d;
        added++;
      } else updated++;
      const fill = (k, v) => { if (v && (d[k] === undefined || d[k] === '' || d[k] === null)) d[k] = v; };
      ['genericAr', 'systemId', 'systemEn', 'systemAr', 'subgroupEn', 'subgroupAr', 'atc', 'introduction',
        'mechanism', 'indications', 'dosage', 'interactions', 'warnings', 'pregnancy'].forEach(k => fill(k, r[k]));
      if (!d.image && r.image) d.image = r.image;
      d.products = d.products || [];
      (r.products || []).forEach(p => {
        const hit = d.products.find(x => norm(x.brand) === norm(p.brand) && (x.strength || '') === (p.strength || '') && (x.form || '') === (p.form || ''));
        if (!hit) {
          d.products.push(Object.assign({ id: Date.now() + Math.random(), verified: false }, p));
          newP++;
        } else {
          let ch = false;
          if (!hit.manufacturer && p.manufacturer) { hit.manufacturer = p.manufacturer; ch = true; }
          if (!hit.country && p.country) { hit.country = p.country; ch = true; }
          if (!hit.agentYemen && p.agentYemen) { hit.agentYemen = p.agentYemen; ch = true; }
          if (!hit.verified && p.verified) { hit.verified = true; ch = true; }
          if (ch) upP++;
        }
      });
    });
    (data.announcements || []).forEach(a => {
      const sid = String(a.id || a.ts || a.body || '').slice(0, 40);
      if (!a.body || MSGS.some(m => String(m.sid || '') === sid)) return;
      MSGS.push({ name: a.author || 'APH Admin', body: a.body, admin: a.admin !== false, ts: a.ts || Date.now(), sid });
      ann++;
    });
    if (!DB.announcements) DB.announcements = [];
    set(K.last, String(Date.now()));
    saveDB();
    renderHome();
    if (typeof renderMsgs === 'function' && document.getElementById('v-msgs').classList.contains('act')) renderMsgs();
    alert(L(`✅ مزامنة ناجحة: +${added} دواء، +${newP} منتج، تحديث ${updated} دواء و${upP} منتج، ${ann} إعلان\n${used}`,
      `✅ Sync OK: +${added} drugs, +${newP} products, ${updated} drugs and ${upP} products updated, ${ann} announcements\n${used}`));
  };

  // --------- AI + sync settings sheet ---------
  APH.settings = function () {
    sheet(`<h3>🧠 ${L('الإعدادات الذكية والمزامنة', 'AI & sync settings')}</h3>
      <label class="f">${L('مزوّد الذكاء الاصطناعي', 'AI provider')}</label>
      <select class="in" id="ap_prov">
        <option value="auto"${APH.provider === 'auto' ? ' selected' : ''}>${L('تلقائي — Gemini ثم OpenAI', 'Auto - Gemini then OpenAI')}</option>
        <option value="gemini"${APH.provider === 'gemini' ? ' selected' : ''}>Google Gemini</option>
        <option value="openai"${APH.provider === 'openai' ? ' selected' : ''}>OpenAI GPT</option>
        <option value="offline"${APH.provider === 'offline' ? ' selected' : ''}>${L('دون إنترنت — قاعدة APH فقط', 'Offline - local APH database only')}</option>
      </select>
      <label class="f">Google AI Studio (Gemini) API key</label><input class="in" id="ap_gk" type="password" value="${esc(APH.geminiKey)}" placeholder="AIza…">
      <label class="f">Gemini model</label><input class="in" id="ap_gm" value="${esc(APH.geminiModel)}">
      <label class="f">OpenAI API key</label><input class="in" id="ap_ok" type="password" value="${esc(APH.openaiKey)}" placeholder="sk-…">
      <label class="f">OpenAI model</label><input class="in" id="ap_om" value="${esc(APH.openaiModel)}">
      <label class="f">${L('رابط القاعدة المنشورة من موقع التحكم', 'Published database URL (control site)')}</label>
      <input class="in" id="ap_url" value="${esc(APH.syncUrl)}">
      <p class="mut">🔒 ${L('تُحفظ المفاتيح في هذا المتصفح فقط ولا تُرفع لأي خادم. إذا شاركته في محادثة فألغه وأنشئ غيره.',
        'Keys are stored in this browser only and never uploaded. If you ever shared one, revoke it and create a new key.')}</p>
      <div class="row" style="margin-top:10px">
        <button class="btn" onclick="APH.saveSettings()">${L('حفظ', 'Save')}</button>
        <button class="btn ghost" onclick="APH.testAI()">${L('اختبار الاتصال', 'Test connection')}</button>
        <button class="btn ghost" onclick="APH.sync()">${L('زامن القاعدة الآن', 'Sync database now')}</button>
        <button class="btn ghost" onclick="window.open('https://aistudio.google.com/app/apikey','_blank')">${L('مفتاح Gemini مجاني', 'Free Gemini key')}</button>
      </div><p class="mut" id="ap_status"></p>`);
  };

  APH.saveSettings = function () {
    set(K.provider, $('ap_prov').value);
    set(K.gemini, $('ap_gk').value.trim());
    set(K.gmodel, $('ap_gm').value.trim() || 'gemini-2.5-flash');
    set(K.openai, $('ap_ok').value.trim());
    set(K.omodel, $('ap_om').value.trim() || 'gpt-4o-mini');
    set(K.url, $('ap_url').value.trim() || DEFAULT_URL);
    const s = $('ap_status');
    if (s) s.textContent = L('✅ حُفظ — المزوّد الحالي: ', '✅ Saved - active provider: ') + APH.active();
    APH.paintBadges();
  };

  APH.testAI = async function () {
    APH.saveSettings();
    const s = $('ap_status');
    s.textContent = L('يختبر…', 'Testing…');
    try {
      const r = await cloud(L('أجب بكلمة واحدة: READY', 'Reply with one word: READY'), null);
      s.textContent = `✅ ${r.provider.toUpperCase()} OK — ${clip(r.text, 40)}`;
    } catch (e) { s.textContent = '❌ ' + e.message; }
  };

  APH.paintBadges = function () {
    document.querySelectorAll('[data-aph-provider]').forEach(el => {
      const p = APH.active();
      el.textContent = p === 'offline'
        ? L('📴 مساعد محلي — أضف مفتاح AI', '📴 Local assistant - add an AI key')
        : '☁ ' + (p === 'gemini' ? 'Gemini (Google AI)' : 'OpenAI GPT');
    });
    const last = Number(get(K.last, '0') || 0);
    document.querySelectorAll('[data-aph-sync]').forEach(el => {
      el.textContent = last ? L('آخر مزامنة: ', 'Last sync: ') + new Date(last).toLocaleString(lang === 'ar' ? 'ar-YE' : 'en') : L('لم تتم مزامنة بعد', 'Never synced');
    });
  };

  // --------- search results: drug → manufacturers → agent & country ---------
  const baseDoSearch = window.doSearch;
  window.doSearch = function () {
    baseDoSearch();
    const q = ($('q').value || '').trim();
    const hits = q && typeof searchDrugs === 'function' ? searchDrugs(q).slice(0, 8) : [];
    const box = $('searchResults');
    if (!box || !hits.length) return;
    hits.forEach(h => {
      const cards = box.querySelectorAll('.card.drug');
      const card = [...cards].find(c => c.getAttribute('onclick') === `openDrug(${h.d.id})`);
      if (!card || card.querySelector('.aph-prods')) return;
      const groups = {};
      (h.d.products || []).forEach(p => { (groups[p.manufacturer || L('شركة غير محددة', 'Unknown manufacturer')] = groups[p.manufacturer || L('شركة غير محددة', 'Unknown manufacturer')] || []).push(p); });
      const keys = Object.keys(groups);
      if (!keys.length) return;
      const wrap = document.createElement('div');
      wrap.className = 'aph-prods';
      wrap.style.cssText = 'margin:-4px 4px 10px;padding:8px 10px;border-inline-start:3px solid #14c8b4;background:rgba(20,200,180,.07);border-radius:10px';
      wrap.innerHTML = `<div class="mut" style="margin-bottom:4px"><b>${L('المنتجات التجارية', 'Trade products')} (${(h.d.products || []).length})</b></div>`
        + keys.map(m => `<div style="margin:4px 0"><b>🏭 ${esc(m)}</b>`
          + groups[m].map(p => `<div class="mut" style="margin-inline-start:8px">• ${esc(p.brand)} ${esc(p.strength || '')} — ${esc(p.form || '')}<br>&nbsp;&nbsp;${L('الدولة', 'Country')}: ${esc(p.country || '—')} | ${L('وكيل اليمن', 'Yemen agent')}: ${esc(p.agentYemen || L('يحتاج توثيق', 'needs verification'))} ${p.verified ? '✅' : '⚠️'}</div>`).join('')
          + '</div>').join('');
      wrap.onclick = ev => { ev.stopPropagation(); openDrug(h.d.id); };
      card.insertAdjacentElement('afterend', wrap);
    });
  };

  // --------- inject UI ---------
  function inject() {
    const aiView = document.getElementById('v-ai');
    if (aiView && !document.getElementById('aphAiBar')) {
      const bar = document.createElement('div');
      bar.id = 'aphAiBar';
      bar.className = 'row';
      bar.style.cssText = 'margin-top:8px;align-items:center';
      bar.innerHTML = `<span class="chip" data-aph-provider style="cursor:pointer" onclick="APH.settings()"></span>
        <label class="btn ghost sm">📷 ${L('تعرف على الدواء من صورته', 'Identify from a photo')}<input type="file" accept="image/*" capture="environment" hidden onchange="aiIdentify(this)"></label>
        <button class="btn ghost sm" onclick="APH.settings()">⚙️ ${L('الإعدادات الذكية', 'AI settings')}</button>`;
      aiView.insertBefore(bar, aiView.querySelector('.chatlog'));
    }
    const more = document.getElementById('v-more');
    if (more && !document.getElementById('aphSyncCard')) {
      const card = document.createElement('div');
      card.className = 'card';
      card.id = 'aphSyncCard';
      card.innerHTML = `<b>☁ ${L('مزامنة القاعدة من موقع التحكم', 'Sync database from the control site')}</b>
        <p class="mut">${L('يسحب كل دواء أو منتج أو وكيل في اليمن أو إعلان ينشره د. عبدالمجيد ويحفظه دائماً في هذا المتصفح.',
          'Downloads every drug, product, Yemen agent and announcement published by Dr. Abdulmajeed and stores them permanently in this browser.')}</p>
        <p class="mut" data-aph-sync></p>
        <div class="row"><button class="btn" onclick="APH.sync()">⬇ ${L('زامن الآن', 'Sync now')}</button>
        <button class="btn ghost" onclick="APH.settings()">🧠 ${L('الإعدادات الذكية ومفاتيح AI', 'AI settings & keys')}</button></div>`;
      more.insertBefore(card, more.children[1]);
    }
    APH.paintBadges();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inject);
  else inject();
  window.addEventListener('hashchange', APH.paintBadges);
})();
