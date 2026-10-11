// Public content only. Authentication and writing are handled by Pages CMS.
export function phoneNumber(value) {
  if (typeof value !== 'string') return null;
  let digits = value.replace(/[\s()+.-]/g, '');
  if (/^0\d{8,9}$/.test(digits)) digits = `972${digits.slice(1)}`;
  return /^[1-9]\d{7,14}$/.test(digits) ? digits : null;
}

export function safeLink(value) {
  if (typeof value !== 'string' || !value.trim()) return null;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function mediaPath(value) {
  if (typeof value !== 'string' || !value.startsWith('/media/')) return null;
  if (/[\\?#]/.test(value)) return null;
  try {
    const decoded = decodeURIComponent(value);
    if (decoded.split('/').some(part => part === '..' || part === '.')) return null;
    if (/[\\?#]/.test(decoded)) return null;
    return value;
  } catch { return null; }
}

export function videoEmbed(value) {
  const safe = safeLink(value);
  if (!safe) return null;
  const url = new URL(safe);
  let id;
  if (['www.youtube.com', 'youtube.com', 'm.youtube.com'].includes(url.hostname)) {
    id = url.pathname === '/watch' ? url.searchParams.get('v') : url.pathname.match(/^\/(?:shorts|embed)\/([^/]+)/)?.[1];
  } else if (url.hostname === 'youtu.be') id = url.pathname.slice(1);
  if (id && /^[\w-]{11}$/.test(id)) return `https://www.youtube-nocookie.com/embed/${id}`;
  if (['vimeo.com', 'www.vimeo.com', 'player.vimeo.com'].includes(url.hostname)) {
    id = url.pathname.match(/^\/(?:video\/)?(\d+)\/?$/)?.[1];
    if (id) return `https://player.vimeo.com/video/${id}`;
  }
  return null;
}

function text(selector, value, root) {
  if (typeof value === 'string') root.querySelector(selector).textContent = value;
}

function updateLink(id, value, root) {
  const link = root.getElementById(id);
  const safe = safeLink(value);
  link.hidden = !safe;
  if (safe) link.href = safe;
}

export function applyContent(data, root = document) {
  if (!data || typeof data !== 'object') return;
  const brand = data.brand || {};
  if (typeof brand.englishName === 'string' && brand.englishName.trim()) {
    const [first, ...rest] = brand.englishName.trim().split(/\s+/);
    const title = root.querySelector('h1');
    title.replaceChildren(root.createTextNode(first));
    if (rest.length) title.append(root.createElement('br'), root.createTextNode(rest.join(' ')));
    root.title = brand.englishName;
  }
  text('.kind', brand.category, root);
  text('.sub', brand.tagline, root);
  text('.end', brand.hebrewName, root);
  text('#gallery-title', data.galleryTitle, root);
  const contact = data.contact || {};
  const phone = phoneNumber(contact.phone);
  const call = root.getElementById('phone-link');
  call.hidden = !phone;
  if (phone) {
    call.href = `tel:+${phone}`;
    text('#phone-label', `התקשרו ${contact.phone}`, root);
  }
  const whatsapp = phoneNumber(contact.whatsapp || contact.phone);
  updateLink('whatsapp-link', whatsapp ? `https://wa.me/${whatsapp}` : '', root);
  text('#navigation-label', `ניווט ל${contact.location || ''}`, root);
  for (const [id, field] of [['navigation', 'navigationUrl'], ['instagram', 'instagram'], ['tiktok', 'tiktok'], ['facebook', 'facebook']]) {
    updateLink(`${id}-link`, contact[field], root);
  }
  const hero = data.hero || {};
  const heroImage = mediaPath(hero.image);
  if (heroImage && /\.(?:jpg|jpeg|png|webp)$/i.test(heroImage)) {
    const img = root.querySelector('.hero img');
    if (img.getAttribute('src') !== heroImage) img.src = heroImage;
    img.alt = typeof hero.alt === 'string' ? hero.alt : brand.hebrewName || '';
  }
  if (Array.isArray(data.gallery)) {
    const figures = [];
    for (const item of data.gallery.slice(0, 40)) {
      if (!item || typeof item !== 'object') continue;
      const src = mediaPath(item.image);
      if (!src || !/\.(?:jpg|jpeg|png|webp)$/i.test(src)) continue;
      const figure = root.createElement('figure');
      const img = root.createElement('img');
      img.src = src;
      img.alt = typeof item.alt === 'string' ? item.alt : item.caption || '';
      img.loading = 'lazy';
      const caption = root.createElement('figcaption');
      caption.textContent = typeof item.caption === 'string' ? item.caption : '';
      figure.append(img, caption);
      figures.push(figure);
    }
    root.querySelector('.rail').replaceChildren(...figures);
    root.getElementById('gallery-title').hidden = figures.length === 0;
  }
  const videos = [];
  for (const item of (Array.isArray(data.videos) ? data.videos : []).slice(0, 12)) {
    if (!item || typeof item !== 'object') continue;
    const figure = root.createElement('figure');
    const src = mediaPath(item.file);
    const embed = videoEmbed(item.externalUrl);
    let player;
    if (src && /\.(?:mp4|m4v|webm)$/i.test(src)) {
      player = root.createElement('video');
      player.src = src;
      player.controls = true;
      player.playsInline = true;
      player.preload = 'none';
      const poster = mediaPath(item.poster);
      if (poster) player.poster = poster;
    } else if (embed) {
      player = root.createElement('iframe');
      player.src = embed;
      player.title = item.title || 'סרטון הווילה';
      player.loading = 'lazy';
      player.allow = 'encrypted-media; picture-in-picture; fullscreen';
      player.allowFullscreen = true;
      player.referrerPolicy = 'strict-origin-when-cross-origin';
    } else if (safeLink(item.externalUrl)) {
      player = root.createElement('a');
      player.href = safeLink(item.externalUrl);
      player.textContent = 'צפייה בסרטון';
      player.className = 'btn';
      player.target = '_blank';
      player.rel = 'noopener noreferrer';
    } else continue;
    const caption = root.createElement('figcaption');
    caption.textContent = typeof item.title === 'string' ? item.title : '';
    figure.append(player, caption);
    videos.push(figure);
  }
  root.getElementById('videos-list').replaceChildren(...videos);
  root.getElementById('videos-section').hidden = videos.length === 0;
  root.documentElement.dataset.contentReady = 'true';
}

if (typeof document !== 'undefined') {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  fetch('/content/site.json', {cache: 'no-cache', signal: controller.signal})
    .then(response => { if (!response.ok) throw new Error('Content unavailable'); return response.json(); })
    .then(data => applyContent(data))
    .catch(() => { /* Preserve the original static card if the content request fails. */ })
    .finally(() => clearTimeout(timeout));
}
