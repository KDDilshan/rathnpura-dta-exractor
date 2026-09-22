/*
 * ikman.lk listing extractor - runs in YOUR browser, on ikman.lk.
 *
 * Why this exists: the crawler in this repo needs network access to ikman.lk.
 * Your browser already has it. This script walks every result page of the
 * current search from inside the page, so same-origin fetch is allowed and no
 * scraping infrastructure is needed, then downloads a JSON file that
 * `ikman-extract import-json` reads directly.
 *
 * HOW TO USE
 *   1. Open the search you want, e.g.
 *      https://ikman.lk/en/ads/ratnapura/land-for-sale
 *   2. Press F12 (or Cmd+Option+I on a Mac) and click the "Console" tab.
 *   3. If the console warns about pasting, type: allow pasting
 *   4. Paste this whole file, press Enter, and wait. Progress prints as it goes.
 *   5. A .json file downloads when it finishes. Send that to the importer.
 *
 * It only reads pages you could click to yourself, one at a time with a pause
 * between them. It does not touch contact details or click "show phone number".
 */
(async () => {
  "use strict";

  const CONFIG = {
    maxPages: 100,          // hard stop, so a mistake cannot loop forever
    delayMs: 1200,          // pause between page fetches; please don't lower it
    startUrl: location.href.split("#")[0],
  };

  const AD_PATH = /^\/(?:en|si|ta)\/ad\/[^/?#]+\/?$/;
  const out = new Map();    // advert URL -> record
  const log = (...a) => console.log("%c[ikman]", "color:#0a7", ...a);

  const clean = (s) =>
    s == null ? null : String(s).replace(/\s+/g, " ").replace(/ /g, " ").trim() || null;

  const abs = (href) => { try { return new URL(href, location.origin).href; } catch { return null; } };

  const isAd = (url) => { try { return AD_PATH.test(new URL(url).pathname); } catch { return false; } };

  const pageParam = (url, n) => {
    const u = new URL(url);
    if (n > 1) u.searchParams.set("page", String(n)); else u.searchParams.delete("page");
    return u.href;
  };

  /* ---- extraction ------------------------------------------------------ */

  // Strategy A: schema.org JSON-LD, the most reliable source when present.
  function fromJsonLd(doc, pageUrl) {
    const found = [];
    const walk = (node, visit) => {
      if (Array.isArray(node)) node.forEach((n) => walk(n, visit));
      else if (node && typeof node === "object") {
        visit(node);
        Object.values(node).forEach((v) => walk(v, visit));
      }
    };
    doc.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
      let data;
      try { data = JSON.parse(s.textContent); } catch { return; }
      walk(data, (node) => {
        const types = [].concat(node["@type"] || []);
        if (!types.some((t) => /Product|Offer|Vehicle|Residence|House|Apartment|Place/i.test(t))) return;
        const url = abs(node.url || node["@id"] || "");
        if (!url || !isAd(url)) return;
        const offer = Array.isArray(node.offers) ? node.offers[0] : node.offers || {};
        found.push({
          url,
          title: clean(node.name),
          price_text: offer.price != null ? `${offer.priceCurrency || "Rs"} ${offer.price}` : null,
          location_text: clean(node.areaServed?.name || node.areaServed),
          description: clean(node.description),
          condition: clean(offer.itemCondition || node.itemCondition),
          images: [].concat(node.image || []).filter((i) => typeof i === "string").map(abs),
          _by: "json-ld",
        });
      });
    });
    return found;
  }

  // Strategy B: the hydration payload the app leaves in the HTML.
  function fromStateBlob(doc) {
    const found = [];
    const patterns = [
      /window\.initialData\s*=\s*(\{[\s\S]*?\})\s*;?\s*<\/script>/,
      /window\.__INITIAL_STATE__\s*=\s*(\{[\s\S]*?\})\s*;?\s*<\/script>/,
      /<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/,
    ];
    const html = doc.documentElement.outerHTML;
    const blobs = [];
    for (const re of patterns) {
      const m = html.match(re);
      if (m) { try { blobs.push(JSON.parse(m[1])); } catch { /* not JSON */ } }
    }
    const pick = (o, keys) => keys.map((k) => o[k]).find((v) => v != null && v !== "");
    const walk = (node) => {
      if (Array.isArray(node)) return node.forEach(walk);
      if (!node || typeof node !== "object") return;
      const raw = pick(node, ["url", "href", "slug", "adUrl", "permalink"]);
      if (typeof raw === "string") {
        const url = abs(raw.startsWith("http") || raw.startsWith("/") ? raw : `/en/ad/${raw}`);
        if (url && isAd(url)) {
          let price = pick(node, ["price", "priceText", "displayPrice", "money"]);
          if (price && typeof price === "object") price = price.amount ?? price.value;
          const loc = pick(node, ["location", "locationName", "area", "city", "town"]);
          found.push({
            url,
            title: clean(pick(node, ["title", "name", "adTitle"])),
            price_text: price != null ? (typeof price === "number" ? `Rs ${price.toLocaleString("en-US")}` : clean(price)) : null,
            location_text: clean(typeof loc === "object" ? loc?.name : loc),
            posted_text: clean(pick(node, ["timeStamp", "postedAt", "displayDate", "age"])),
            category: clean(pick(node, ["categoryName", "category"])),
            promoted: Boolean(node.isPromoted || node.promoted || node.isFeatured),
            images: [].concat(node.images || node.image || []).map((i) => abs(typeof i === "string" ? i : i?.url)).filter(Boolean),
            _by: "state-blob",
          });
        }
      }
      Object.values(node).forEach(walk);
    };
    blobs.forEach(walk);
    return found;
  }

  // Strategy C: read each advert anchor's surrounding card. Keys only on the
  // advert URL shape, so it survives class-name changes.
  function fromCards(doc) {
    const found = [];
    const priceRe = /(?:Rs\.?|LKR|රු)\s*[\d,]+/i;
    const dateRe = /\b(?:\d+\s*(?:second|minute|min|hour|hr|day|week|month|year)s?\s+ago|today|yesterday|just now)\b/i;
    const sizeRe = /[\d.,]+\s*(?:perch(?:es)?|acres?|sq\.?\s?(?:ft|m))/i;
    const seen = new Set();

    doc.querySelectorAll("a[href]").forEach((a) => {
      const url = abs(a.getAttribute("href"));
      if (!url || !isAd(url) || seen.has(url)) return;
      seen.add(url);

      // Climb to the nearest ancestor that still holds only this one advert.
      let card = a;
      for (let i = 0; i < 4; i++) {
        const p = card.parentElement;
        if (!p || p === doc.body) break;
        const ads = new Set(
          [...p.querySelectorAll("a[href]")].map((x) => abs(x.getAttribute("href"))).filter((h) => h && isAd(h))
        );
        if (ads.size > 1) break;
        card = p;
      }

      const texts = [...card.querySelectorAll("*")]
        .map((n) => (n.children.length === 0 ? clean(n.textContent) : null))
        .filter(Boolean);

      found.push({
        url,
        title: clean(a.getAttribute("title")) || clean(a.textContent) || texts.find((t) => t.length > 12) || null,
        price_text: texts.find((t) => priceRe.test(t)) || null,
        size_text: texts.find((t) => sizeRe.test(t)) || null,
        posted_text: texts.find((t) => dateRe.test(t)) || null,
        location_text: texts.find((t) => !priceRe.test(t) && !dateRe.test(t) && !sizeRe.test(t) && /,/.test(t)) || null,
        promoted: /promot|feature|urgent|top.?ad/i.test(card.className || ""),
        images: [...card.querySelectorAll("img")].map((i) => abs(i.getAttribute("src") || i.getAttribute("data-src"))).filter(Boolean),
        _by: "cards",
      });
    });
    return found;
  }

  // Merge every strategy's read of the page: whichever saw a field, keeps it.
  function extract(doc, pageUrl) {
    const merged = new Map();
    for (const rec of [...fromJsonLd(doc, pageUrl), ...fromStateBlob(doc), ...fromCards(doc)]) {
      const prev = merged.get(rec.url) || { url: rec.url, images: [], _by: [] };
      for (const [k, v] of Object.entries(rec)) {
        if (k === "_by") { if (!prev._by.includes(v)) prev._by.push(v); continue; }
        if (k === "images") { prev.images = [...new Set([...(prev.images || []), ...(v || [])])]; continue; }
        if (v != null && v !== "" && (prev[k] == null || prev[k] === "")) prev[k] = v;
      }
      merged.set(rec.url, prev);
    }
    return [...merged.values()];
  }

  /* ---- walk the result pages ------------------------------------------- */

  const totalText = clean(document.body.innerText.match(/([\d,]+)\+?\s+(?:Lands?|Ads?|Results?|Properties)/i)?.[0]);
  log(`starting at ${CONFIG.startUrl}`);
  if (totalText) log(`page reports: ${totalText}`);

  for (let page = 1; page <= CONFIG.maxPages; page++) {
    const url = pageParam(CONFIG.startUrl, page);
    let doc;
    if (page === 1) {
      doc = document;                       // already loaded; don't refetch
    } else {
      await new Promise((r) => setTimeout(r, CONFIG.delayMs));
      let res;
      try { res = await fetch(url, { credentials: "same-origin" }); }
      catch (e) { log(`page ${page}: network error, stopping -`, e.message); break; }
      if (!res.ok) { log(`page ${page}: HTTP ${res.status}, stopping`); break; }
      doc = new DOMParser().parseFromString(await res.text(), "text/html");
    }

    const rows = extract(doc, url);
    const before = out.size;
    rows.forEach((r) => { if (!out.has(r.url)) out.set(r.url, { ...r, source_page: url }); });
    const added = out.size - before;

    log(`page ${page}: found ${rows.length}, new ${added}, total ${out.size}`);
    if (rows.length === 0) { log("no listings on this page - reached the end"); break; }
    if (added === 0 && page > 1) { log("nothing new - pagination is repeating, stopping"); break; }
  }

  /* ---- hand back the results ------------------------------------------- */

  const records = [...out.values()];
  const payload = {
    extracted_at: new Date().toISOString(),
    source_url: CONFIG.startUrl,
    reported_total: totalText,
    count: records.length,
    listings: records,
  };

  console.log("%c[ikman] DONE", "color:#0a7;font-weight:bold", `${records.length} unique adverts`);
  console.table(records.slice(0, 10).map((r) => ({
    title: (r.title || "").slice(0, 44), price: r.price_text, size: r.size_text, where: r.location_text,
  })));

  const name = `ikman-${CONFIG.startUrl.replace(/^https?:\/\/[^/]+\//, "").replace(/[^a-z0-9]+/gi, "-")}-${Date.now()}.json`;
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  log(`downloaded ${name} - send this file to: ikman-extract import-json <file>`);

  window.ikmanResults = payload;   // also left here if the download is blocked
  return payload;
})();
