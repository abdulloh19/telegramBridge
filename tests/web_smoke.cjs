const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require('puppeteer-core');
const ts = require('../../mnemonic-webapp/node_modules/typescript');

function loadWords() {
  const source = fs.readFileSync(path.resolve(__dirname, '../../mnemonic-webapp/src/data/words.ts'), 'utf8');
  const js = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
  const module = {exports: {}};
  new Function('exports', 'require', 'module', js)(module.exports, require, module);
  return module.exports.MNEMONIC_WORDS;
}

(async () => {
  const words = loadWords();
  const browser = await puppeteer.launch({executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true});
  try {
    const page = await browser.newPage();
    await page.setViewport({width: 390, height: 844});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setRequestInterception(true);
    page.on('request', request => {
      if (request.url().includes('/api/users')) return request.respond({status: 200, contentType: 'application/json', body: JSON.stringify({success: true, users: [], totalUsers: 0, activeTodayCount: 0})});
      if (request.url().includes('/api/tts')) return request.respond({status: 503, body: ''});
      if (!request.url().startsWith('http://127.0.0.1:3107')) return request.abort();
      return request.continue();
    });
    let count = 0;
    for (const lang of ['en', 'ru']) {
      for (const level of ['BEGINNER', 'INTERMEDIATE', 'ADVANCED']) {
        assert(words.filter(w => w.language === lang && w.level === level).length >= 5, `${lang}/${level} word pool`);
        for (const tab of ['dashboard', 'lesson', 'grammar', 'games', 'dialogue', 'practice', 'quiz', 'search', 'vocabulary']) {
          console.log(`CHECK ${lang}/${level}/${tab}`);
          await page.goto(`http://127.0.0.1:3107/?lang=${lang}&level=${level}&tab=${tab}`, {waitUntil: 'networkidle0'});
          await page.waitForFunction(() => document.querySelector('main')?.innerText.length > 20);
          if (tab === 'games') {
            for (const mode of ['flashcards', 'match', 'scramble', 'sort']) {
              await page.click(`#btn-game-${mode}`);
              await page.waitForFunction(id => document.getElementById(id)?.className.includes('bg-gradient'), {}, `btn-game-${mode}`);
            }
          }
          assert.equal(errors.length, 0, errors.join('\n'));
          count++;
        }
        // Answer every practice question correctly and exercise the manual next button.
        await page.goto(`http://127.0.0.1:3107/?lang=${lang}&level=${level}&tab=practice`, {waitUntil: 'networkidle0'});
        for (let index = 0; index < 5; index++) {
          console.log(`ANSWER ${lang}/${level}/${index + 1}`);
          await page.waitForFunction(i => document.querySelector('main')?.textContent.includes(`Savol ${i + 1}:`), {}, index);
          const display = await page.$eval('main span.text-2xl', el => el.textContent.trim());
          const target = words.find(w => w.language === lang && w.level === level && (index % 2 === 0 ? w.word === display : w.uzbekMeaning === display));
          assert(target, `Question word: ${display}`);
          const answer = index % 2 === 0 ? target.uzbekMeaning : target.word;
          await page.evaluate(answer => {
            const span = [...document.querySelectorAll('main button span.text-base')].find(el => el.textContent.trim() === answer);
            if (!span) throw Error('Answer missing');
            span.closest('button').click();
          }, answer);
          await page.waitForFunction(() => [...document.querySelectorAll('main button')].some(b => /Keyingi savol|Natijalarni/.test(b.innerText)));
          await page.evaluate(() => [...document.querySelectorAll('main button')].find(b => /Keyingi savol|Natijalarni/.test(b.innerText)).click());
        }
        const stats = await page.evaluate(() => JSON.parse(localStorage.getItem('mnemo_stats')));
        assert.equal(stats.quizScores % 50, 0, 'Perfect practice must add exactly 50 points');
        console.log(`PASS ${lang}/${level}: 9 pages and complete practice`);
      }
    }
    console.log(`PASS ${count} page/language/level combinations; 6 completed practices; ${errors.length} browser errors`);
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
