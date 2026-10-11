// Test dependencies: npm install --prefix qa/content-deps --no-save jsdom yaml
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {phoneNumber, safeLink, mediaPath, videoEmbed, applyContent} from '../assets/card.mjs';

const require = createRequire(new URL('../qa/content-deps/test.cjs', import.meta.url));
const {JSDOM} = require('jsdom');
const YAML = require('yaml');
const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const settings = JSON.parse(read('content/site.json'));
const document = () => new JSDOM(read('index.html'), {url:'https://ahuzatmenashe.github.io/'}).window.document;

test('local and international phone links and unsafe inputs', () => {
  assert.equal(phoneNumber('052-333-8028'), '972523338028');
  assert.equal(phoneNumber('+972 (52) 333 8028'), '972523338028');
  assert.equal(phoneNumber('+1 212 555 0123'), '12125550123');
  for (const value of ['123', 'javascript:alert(1)', '0523338028?x=1', null]) assert.equal(phoneNumber(value), null);
  for (const value of ['javascript:alert(1)', 'data:text/html,x', 'http://example.org', 'https://user:pass@example.org']) assert.equal(safeLink(value), null);
  for (const value of ['/media/../index.html', '/media/%2e%2e/a.jpg', '//evil.org/a.jpg', '/media/a.jpg?x=1', '/media/%5ca.jpg']) assert.equal(mediaPath(value), null);
  assert.equal(mediaPath('/media/images/a.jpg'), '/media/images/a.jpg');
  assert.equal(videoEmbed('https://youtu.be/dQw4w9WgXcQ'), 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ');
  assert.equal(videoEmbed('https://vimeo.com/123456'), 'https://player.vimeo.com/video/123456');
  assert.equal(videoEmbed('https://youtube.com.evil.org/watch?v=dQw4w9WgXcQ'), null);
});

test('CMS schema covers editable JSON and existing media', () => {
  const config = YAML.parse(read('.pages.yml'));
  assert.equal(config.content[0].path, 'content/site.json');
  const check = (fields, value) => {
    for (const field of fields) {
      assert.ok(Object.hasOwn(value, field.name), `Missing ${field.name}`);
      if (field.fields && !field.list) check(field.fields, value[field.name]);
      if (field.fields && field.list) value[field.name].forEach(item => check(field.fields, item));
    }
  };
  check(config.content[0].fields, settings);
  assert.deepEqual(config.media.map(media => media.name), ['images', 'videos']);
  for (const item of [settings.hero, ...settings.gallery]) {
    assert.ok(readFileSync(new URL(`..${item.image}`, import.meta.url)).length > 100);
  }
});

test('saved content changes contact, brand, gallery and video players safely', () => {
  const doc = document();
  const content = structuredClone(settings);
  content.contact.phone = '050-123-4567';
  content.contact.instagram = 'https://instagram.com/new_profile';
  content.contact.facebook = 'javascript:alert(1)';
  content.brand.hebrewName = '<img src=x onerror=alert(1)>';
  content.gallery = [content.gallery[2], content.gallery[0], null, {image:'https://evil.org/x.jpg'}];
  content.videos = [
    {file:'/media/videos/clip.mp4', poster:settings.hero.image, title:'סיור'},
    {externalUrl:'https://youtu.be/dQw4w9WgXcQ', title:'סרטון'},
    null, {externalUrl:'javascript:alert(1)'}
  ];
  applyContent(content, doc);
  assert.equal(doc.getElementById('phone-link').href, 'tel:+972501234567');
  assert.equal(doc.getElementById('whatsapp-link').href, 'https://wa.me/972501234567');
  assert.equal(doc.getElementById('instagram-link').href, content.contact.instagram);
  assert.ok(doc.getElementById('facebook-link').hidden);
  assert.equal(doc.querySelector('.end').textContent, content.brand.hebrewName);
  assert.equal(doc.querySelector('.end img'), null);
  assert.deepEqual([...doc.querySelectorAll('.rail img')].map(img => img.getAttribute('src')), [settings.gallery[2].image, settings.gallery[0].image]);
  assert.equal(doc.querySelectorAll('#videos-list figure').length, 2);
  const video = doc.querySelector('video');
  assert.ok(video.controls && video.playsInline && !video.autoplay);
  assert.equal(video.preload, 'none');
  assert.equal(doc.querySelector('iframe').src, 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ');
  assert.equal(doc.documentElement.dataset.contentReady, 'true');
  applyContent({...settings, gallery:[], videos:[]}, doc);
  assert.ok(doc.getElementById('gallery-title').hidden && doc.getElementById('videos-section').hidden);
});

test('failed content request preserves the original card', async () => {
  const doc = document();
  const before = doc.body.innerHTML;
  const savedFetch = globalThis.fetch;
  globalThis.document = doc;
  globalThis.fetch = async () => ({ok:false});
  try {
    await import(`../assets/card.mjs?fallback=${Date.now()}`);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(doc.body.innerHTML, before);
    assert.equal(doc.documentElement.dataset.contentReady, undefined);
  } finally {
    delete globalThis.document;
    globalThis.fetch = savedFetch;
  }
});
