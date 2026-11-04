// The viewer and its exports share the figure layout, but never the viewing zoom.
const FigureImage = (() => {
  const kinds = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif', 'image/webp': 'webp', 'image/svg+xml': 'svg',
    'image/apng': 'png', 'image/avif': 'avif', 'image/tiff': 'tiff', 'image/bmp': 'bmp' };
  const selector = 'img, svg';
  const resources = (body) => [...body.querySelectorAll(selector)].filter((el) =>
    !el.parentElement.closest('svg') && !el.closest('math, .ltx_Math, .ltx_equation, .ltx_equationgroup, .pf-tex, [role="math"], [role="presentation"], [aria-hidden="true"], .ltx_icon'));

  function at(target) {
    let pic = target.closest(selector);
    for (let outer; pic && (outer = pic.parentElement?.closest('svg'));) pic = outer;
    return pic;
  }

  function size(pic) {
    if (pic instanceof HTMLImageElement) return [pic.naturalWidth, pic.naturalHeight];
    const vb = pic.viewBox.baseVal;
    return [pic.width.baseVal.unitType === 1 ? pic.width.baseVal.value : vb.width || pic.clientWidth || 300,
      pic.height.baseVal.unitType === 1 ? pic.height.baseVal.value : vb.height || pic.clientHeight || 150];
  }

  const isRasterData = (url) => /^data:image\/(?:png|jpeg|gif|webp|avif|apng)[;,]/i.test(url);
  const safeCss = (css) => !/@import|expression\s*\(|\\|(?:javascript|vbscript):|url\s*\(/i
    .test(css.replace(/url\(\s*['"]?#[\w.:-]+['"]?\s*\)/gi, ''));

  async function readImage(url) {
    if (url.protocol !== 'data:' && !(url.origin === location.origin && /^https?:$/.test(url.protocol))) throw new Error('resource');
    const response = await fetch(url, { redirect: 'error' });
    if (!response.ok) throw new Error('resource');
    const blob = await response.blob();
    if (!Object.hasOwn(kinds, blob.type) || !blob.size) throw new Error('resource');
    if (blob.type !== 'image/svg+xml') {
      const head = [...new Uint8Array(await blob.slice(0, 16).arrayBuffer())].map((b) => b.toString(16).padStart(2, '0')).join('');
      const signatures = {
        png: /^89504e470d0a1a0a/, jpg: /^ffd8ff/, gif: /^474946383[79]61/, webp: /^52494646.{8}57454250/,
        bmp: /^424d/, tiff: /^(49492a00|4d4d002a)/, avif: /^.{8}667479706176696[36]/,
      };
      if (!signatures[kinds[blob.type]].test(head)) throw new Error('resource');
    }
    return blob;
  }

  // An SVG embedded as an image is passive. A copy opened on its own must also be safe
  // as a document, and must carry any cached raster images used inside a TikZ drawing.
  async function standaloneSvg(svg, originalBlob) {
    if (svg.localName !== 'svg' || svg.namespaceURI !== 'http://www.w3.org/2000/svg') throw new Error('resource');
    let changed = false;
    for (const el of [svg, ...svg.querySelectorAll('*')]) {
      const tag = el.localName.toLowerCase();
      if (/^(script|iframe|object|embed|form|base|meta|link|frame|frameset|applet|audio|video|source|animate|set|discard)$/.test(tag)
          || (tag === 'style' && !safeCss(el.textContent))) {
        el.remove();
        changed = true;
        continue;
      }
      for (const attr of [...el.attributes]) {
        const name = attr.localName.toLowerCase(), url = attr.value.trim();
        if (name.startsWith('on') || name === 'srcset' || (attr.prefix === 'xml' && name === 'base') || (name === 'style' && !safeCss(url))) {
          el.removeAttributeNode(attr);
          changed = true;
        } else if (name === 'href' || name === 'src') {
          if (url.startsWith('#') || isRasterData(url)) continue;
          let src;
          try { src = new URL(url, location.href); } catch { /* malformed reference */ }
          const cached = src && /^\/p\/[\w.-]+\/img\/[\w.-]+$/.test(src.pathname) && src.origin === location.origin;
          if (cached && (tag === 'image' || tag === 'img')) {
            const data = await readImage(src);
            if (data.type !== 'image/svg+xml') {
              attr.value = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = reject;
                reader.readAsDataURL(data);
              });
              changed = true;
              continue;
            }
          }
          if (/^(img|image|use|feimage)$/.test(tag)) throw new Error('resource');
          el.removeAttributeNode(attr);
          changed = true;
        }
      }
    }
    return originalBlob && !changed ? originalBlob
      : new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml' });
  }

  async function original(pic) {
    if (!(pic instanceof HTMLImageElement)) {
      const svg = pic.cloneNode(true);
      svg.removeAttribute('draggable');
      svg.classList.remove('lb-selected');
      const [w, h] = size(pic);
      svg.setAttribute('width', w);
      svg.setAttribute('height', h);
      if (!svg.hasAttribute('viewBox')) svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
      return standaloneSvg(svg);
    }
    // A failed cache lookup can leave an external URL. Export only resources served with the reader.
    const blob = await readImage(new URL(pic.currentSrc || pic.src));
    if (blob.type !== 'image/svg+xml') return blob;
    const parsed = new DOMParser().parseFromString(await blob.text(), 'image/svg+xml');
    return standaloneSvg(parsed.documentElement, parsed.doctype || [...parsed.childNodes].some((n) => n.nodeType === Node.PROCESSING_INSTRUCTION) ? null : blob);
  }

  async function withImage(blob, draw) {
    const svg = blob.type === 'image/svg+xml' ? await blob.text() : '';
    // Chromium treats foreignObject in blob URLs as cross-origin for canvas drawing.
    const inline = /<foreignObject[\s>]/i.test(svg);
    const url = inline ? `data:image/svg+xml,${encodeURIComponent(svg)}` : URL.createObjectURL(blob);
    try {
      const image = new Image();
      image.src = url;
      await image.decode();
      return draw(image);
    } finally { if (!inline) URL.revokeObjectURL(url); }
  }

  function canvas(w, h) {
    // Bound the RGBA backing store to 128 MiB, and stay below the per-side limits of the supported engines.
    w = Math.ceil(w); h = Math.ceil(h);
    if (w > 8192 || h > 8192 || w * h > 32 * 1024 * 1024) throw new Error('size');
    if (!(w > 0 && h > 0)) throw new Error('resource');
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    return c;
  }

  async function png(c) {
    try {
      return await new Promise((resolve, reject) => c.toBlob((b) => b ? resolve(b) : reject(new Error('resource')), 'image/png'));
    } finally { c.width = c.height = 0; }
  }

  function single(pic, copy) {
    return original(pic).then((blob) => withImage(blob, (image) => {
      if (!copy) return blob;
      const c = canvas(image.naturalWidth, image.naturalHeight);
      c.getContext('2d').drawImage(image, 0, 0);
      return png(c);
    }));
  }

  function panelLabel(pic, body) {
    for (let el = pic.parentElement; el && el !== body; el = el.parentElement) {
      const tag = el.querySelector(':scope > :is(figcaption, .ltx_caption) .ltx_tag, :scope > :is(figcaption, .ltx_caption):not(:has(*))');
      if (tag) return tag;
    }
    return null;
  }

  async function group(pics, labels, body) {
    // Freeze the coordinates before the caller can navigate. All rectangles are in the unzoomed layout.
    const layoutPixel = (n) => Math.round(n * 64) / 64;
    const bounds = (el) => {
      // SVG does not have offsetWidth or offsetLeft. CSS transforms uniformly scale the entire layout.
      const r = el.getBoundingClientRect(), base = body.getBoundingClientRect();
      const scale = base.width / body.offsetWidth;
      return { x: layoutPixel((r.left - base.left) / scale), y: layoutPixel((r.top - base.top) / scale),
        w: layoutPixel(r.width / scale), h: layoutPixel(r.height / scale) };
    };
    const panels = pics.map((pic) => ({ pic, ...bounds(pic) }));
    const tags = [...new Set(labels.filter(Boolean))].map((tag) => {
      const css = getComputedStyle(tag);
      return { ...bounds(tag), text: tag.textContent.trim(), font: `${css.fontWeight} ${css.fontSize} ${css.fontFamily}` };
    }).filter((tag) => tag.text && tag.w && tag.h);
    const boxes = panels.concat(tags);
    const x = Math.min(...boxes.map((b) => b.x)), y = Math.min(...boxes.map((b) => b.y));
    const w = Math.max(...boxes.map((b) => b.x + b.w)) - x, h = Math.max(...boxes.map((b) => b.y + b.h)) - y;
    const blobs = await Promise.all(pics.map(original));
    // Size by the densest panel so none of the available bitmap pixels are thrown away.
    let density = 1;
    for (let i = 0; i < panels.length; i++) {
      const panel = panels[i];
      if (!(panel.w > 0 && panel.h > 0)) throw new Error('resource');
      const scale = await withImage(blobs[i], (image) => Math.max(image.naturalWidth / panel.w, image.naturalHeight / panel.h));
      density = Math.max(density, scale);
    }
    const c = canvas(w * density, h * density);
    try {
      const ctx = c.getContext('2d');
      ctx.scale(density, density);
      ctx.translate(-x, -y);
      for (let i = 0; i < panels.length; i++) {
        const b = panels[i];
        await withImage(blobs[i], (image) => ctx.drawImage(image, b.x, b.y, b.w, b.h));
      }
      ctx.fillStyle = '#222';
      ctx.textBaseline = 'middle';
      for (const tag of tags) {
        ctx.font = tag.font;
        ctx.fillText(tag.text, tag.x, tag.y + tag.h / 2, tag.w);
      }
      return await png(c);
    } finally { c.width = c.height = 0; }
  }

  const extension = (blob) => kinds[blob.type];
  return { resources, at, size, panelLabel, single, group, extension };
})();
