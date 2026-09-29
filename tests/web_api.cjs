const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('../../mnemonic-webapp/node_modules/typescript');
const source = fs.readFileSync(require('node:path').resolve(__dirname, '../../mnemonic-webapp/src/app/api/users/route.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, esModuleInterop: true}}).outputText;
let stored = '{}';
const fakeFs = {existsSync: () => true, readFileSync: () => stored, writeFileSync: (_path, data) => {stored = data;}};
const api = {exports: {}};
new Function('exports', 'require', 'module', compiled)(api.exports, name => {
  if (name === 'fs') return fakeFs;
  if (name === 'next/server') return require('../../mnemonic-webapp/node_modules/next/server');
  return require(name);
}, api);
async function post(data) {
  return api.exports.POST(new Request('http://localhost/api/users', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)}));
}
(async () => {
  assert.equal((await post({})).status, 400);
  await post({chatId: 123, language: 'en'});
  assert.equal(JSON.parse(stored)['123'].totalWordsLearned, 0);
  const complete = {chatId: 123, language: 'en', action: 'complete_word', wordId: 'en_test'};
  await post(complete);
  await post(complete);
  assert.equal(JSON.parse(stored)['123'].totalWordsLearned, 1);
  await post({...complete, deltaWordsEn: -1});
  await post({...complete, deltaWordsEn: -1});
  assert.equal(JSON.parse(stored)['123'].totalWordsLearned, 0);
  await post({chatId: 123, language: 'en', wordIndex: 20});
  assert.equal(JSON.parse(stored)['123'].totalWordsLearned, 0);
  const result = await (await api.exports.GET(new Request('http://localhost/api/users'))).json();
  assert.equal(result.totalUsers, 1);
  console.log('PASS API: missing ID, zero initial progress, idempotent completion/undo, browsing does not mark learned, unseeded count');
})().catch(error => {console.error(error); process.exitCode = 1;});
