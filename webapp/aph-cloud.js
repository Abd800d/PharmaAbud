/* AbdulmajeedPharma (APH) — Cloud layer for the web app
   © Dr. Abdulmajeed Abdullah Almakhedhi — WhatsApp 781733795 • 7a8b1d@gmail.com
   يضيف: ذكاء اصطناعي حقيقي (Gemini / OpenAI)، التعرف على الدواء من صورته،
   مزامنة القاعدة من موقع التحكم، ونتائج بحث مقسّمة (دواء ← شركات ← وكيل ودولة).
   يعمل دون إنترنت: كل دالة ترجع تلقائياً للوضع المحلي عند الفشل. */
(function () {
  'use strict';
  const K = {
    provider: 'aph_ai_provider', proxy: 'aph_ai_proxy',
    gmodel: 'aph_gemini_model', omodel: 'aph_openai_model', url: 'aph_sync_url',
    last: 'aph_last_sync',
  };
  const DEFAULT_URL = 'https://raw.githubusercontent.com/Abd800d/PharmaAbud/main/webapp/aph-database.json';
  const get = (k, d) => localStorage.getItem(k) || d;
  const set = (k, v) => localStorage.setItem(k, v);
  // Remove credentials saved by old client-side versions. Browser storage is not a secret store.
  localStorage.removeItem('aph_gemini_key');
  localStorage.removeItem('aph_openai_key');
  function safeProxy(value) {
    try {
      const u = new URL(String(value || '').trim());
      return u.protocol === 'https:' && !!u.hostname && !u.username && !u.password
        && !u.search && !u.hash && !/(AIza[0-9A-Za-z_-]{12,}|sk-[A-Za-z0-9_-]{12,})/.test(value);
    } catch (_) { return false; }
  }
  const APH = {
    get provider() { return get(K.provider, 'auto'); },
    get proxyUrl() { return get(K.proxy, '').trim(); },
    get geminiModel() { return get(K.gmodel, 'gemini-2.5-flash'); },
    get openaiModel() { return get(K.omodel, 'gpt-4o-mini'); },
    get syncUrl() { return get(K.url, DEFAULT_URL); },
    hasCloud() { return safeProxy(APH.proxyUrl); },
    active() {
      if (APH.provider === 'offline' || !APH.hasCloud()) return 'offline';
      return APH.provider === 'openai' ? 'openai' : 'gemini';
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

  async function cloud(prompt, dataUrl, requestedProvider) {
    if (!APH.hasCloud()) throw new Error('Secure AI Worker URL is missing or invalid.');
    const provider = requestedProvider || (APH.provider === 'openai' ? 'openai' : 'gemini');
    let image = '', mime = 'image/jpeg';
    if (dataUrl) {
      const comma = dataUrl.indexOf(',');
      const header = dataUrl.slice(0, comma);
      image = dataUrl.slice(comma + 1);
      mime = (header.match(/^data:([^;]+);base64/i) || [])[1] || 'image/jpeg';
      if (image.length > 7 * 1024 * 1024) throw new Error('Image is too large for the secure AI service.');
    }
    const response = await fetch(APH.proxyUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider,
        model: provider === 'openai' ? APH.openaiModel : APH.geminiModel,
        system: SYSTEM,
        prompt,
        maxTokens: 1400,
        ...(image ? { image, mime } : {}),
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(`Secure AI HTTP ${response.status}: ${clip(data.error || 'Request failed', 220)}`);
    const text = String(data.text || '').trim();
    if (!text) throw new Error('AI provider returned an empty answer.');
    return { text, provider: data.provider || provider };
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
    if (!APH.hasCloud()) {
      alert(L('يجب ضبط رابط خادم الذكاء الاصطناعي الآمن أولاً من الإعدادات الذكية.',
        'Configure the secure AI server URL first in AI settings.'));
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
        <option value="auto"${APH.provider === 'auto' ? ' selected' : ''}>${L('تلقائي — Gemini فقط، دون تحويل إلى مدفوع', 'Automatic — Gemini only; no paid fallback')}</option>
        <option value="gemini"${APH.provider === 'gemini' ? ' selected' : ''}>Google Gemini</option>
        <option value="openai"${APH.provider === 'openai' ? ' selected' : ''}>OpenAI GPT (may be paid)</option>
        <option value="offline"${APH.provider === 'offline' ? ' selected' : ''}>${L('دون إنترنت — قاعدة APH فقط', 'Offline - local APH database only')}</option>
      </select>
      <label class="f">${L('رابط Cloudflare Worker العام (ليس سراً)', 'Public Cloudflare Worker URL (not a secret)')}</label>
      <input class="in" id="ap_proxy" value="${esc(APH.proxyUrl)}" placeholder="https://aph-ai-proxy.example.workers.dev">
      <label class="f">Gemini model</label><input class="in" id="ap_gm" value="${esc(APH.geminiModel)}">
      <label class="f">OpenAI model</label><input class="in" id="ap_om" value="${esc(APH.openaiModel)}">
      <label class="f">${L('رابط القاعدة المنشورة من موقع التحكم', 'Published database URL (control site)')}</label>
      <input class="in" id="ap_url" value="${esc(APH.syncUrl)}">
      <p class="mut">🔒 ${L('لا تضع مفتاح API هنا. احفظ GEMINI_API_KEY كسرّ في Cloudflare Worker. حصة Gemini المجانية قد تتغير؛ OpenAI قد يكون مدفوعاً.',
        'Never enter an API key here. Store GEMINI_API_KEY as a Cloudflare Worker Secret. Gemini free quota may change; OpenAI may be paid.')}</p>
      <div class="row" style="margin-top:10px">
        <button class="btn" onclick="APH.saveSettings()">${L('حفظ', 'Save')}</button>
        <button class="btn ghost" onclick="APH.testAI()">${L('اختبار الاتصال', 'Test connection')}</button>
        <button class="btn ghost" onclick="APH.sync()">${L('زامن القاعدة الآن', 'Sync database now')}</button>
      </div><p class="mut" id="ap_status"></p>`);
  };

  APH.saveSettings = function () {
    const proxy = $('ap_proxy').value.trim();
    const s = $('ap_status');
    if (proxy && !safeProxy(proxy)) {
      if (s) s.textContent = L('رابط غير صالح: أدخل HTTPS Worker URL فقط، ولا تلصق مفتاح API.',
        'Invalid URL: enter an HTTPS Worker URL only; never paste an API key.');
      return false;
    }
    set(K.provider, $('ap_prov').value);
    set(K.proxy, proxy);
    set(K.gmodel, $('ap_gm').value.trim() || 'gemini-2.5-flash');
    set(K.omodel, $('ap_om').value.trim() || 'gpt-4o-mini');
    set(K.url, $('ap_url').value.trim() || DEFAULT_URL);
    if (s) s.textContent = L('✅ حُفظت الإعدادات — مفاتيح المزوّد لا توجد في المتصفح.',
      '✅ Settings saved — provider keys are not stored in this browser.');
    APH.paintBadges();
    return true;
  };

  APH.testAI = async function () {
    if (!APH.saveSettings()) return;
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
        ? L('📴 مساعد محلي — اضبط خادم AI الآمن', '📴 Local assistant - configure the secure AI server')
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
        <button class="btn ghost" onclick="APH.settings()">🧠 ${L('الإعدادات الذكية', 'AI settings')}</button></div>`;
      more.insertBefore(card, more.children[1]);
    }
    APH.paintBadges();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inject);
  else inject();
  window.addEventListener('hashchange', APH.paintBadges);
})();
