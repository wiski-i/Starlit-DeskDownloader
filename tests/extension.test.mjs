import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const source = await readFile(new URL('../browser_extension/bridge.js', import.meta.url), 'utf8');
const {canSend, sendLink, getProfiles} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

const cases = JSON.parse(await readFile(new URL('./url-cases.json', import.meta.url), 'utf8'));

test('shared URL vectors match the native request boundary', () => {
  for (const entry of cases) assert.equal(canSend(entry.url), entry.accepted, entry.url);
});

test('URL boundary rejects browser-normalized malformed addresses', () => {
  for (const url of ['https://example.com/a?x=1#b', 'HTTP://localhost:8080/', 'https://[::1]:443/', 'https://örnek.test/çağrı', 'https://example.com/' + 'a'.repeat(8172)]) {
    assert.equal(canSend(url), true, url);
  }
  for (const url of [null, '', 'file:///tmp/a', 'https:example.com', 'https:/example.com', 'https:///example.com', 'https:////example.com', 'https://', 'https://user:pass@example.com', 'https://@example.com', 'https://example.com:', 'https://example.com:65536', 'https://example.com:abc', 'https://example.com\\evil', 'https://example.com/a b', 'https://example.com/\nfoo', 'https://exam\tple.com/', 'https://example.com/\u007f', 'https://example.com/' + 'a'.repeat(8173), 'https://example.com/' + 'ğ'.repeat(4087)]) {
    assert.equal(canSend(url), false, String(url));
  }
});

test('profile request and native host failures retain protocol behavior', async () => {
  const requests = [];
  globalThis.chrome = {runtime: {sendNativeMessage: async (host, request) => {
    requests.push({host, request});
    return {status: 'accepted'};
  }}};
  const profile = {format: 'mp4', quality: '720'};
  assert.equal(await sendLink('https://example.com/çağrı', profile), 'accepted');
  assert.deepEqual(requests, [{host: 'com.starlit.deskdownloader', request: {action: 'download', url: 'https://example.com/çağrı', profile}}]);
  assert.equal(await sendLink('file:///tmp/a', profile), 'invalid_url');
  assert.equal(requests.length, 1);
  chrome.runtime.sendNativeMessage = async () => ({status: 'invalid_url'});
  assert.deepEqual(await getProfiles(), {status: 'upgrade_required'});
  chrome.runtime.sendNativeMessage = async () => {throw new Error('Host missing');};
  assert.equal(await sendLink('https://example.com'), 'desktop_unavailable');
  assert.deepEqual(await getProfiles(), {status: 'desktop_unavailable'});
});
