/* Run: NODE_PATH=/path/to/playwright/node_modules node tests/polls.browser.cjs
   All site assets are local routes and every collector request is mocked. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const out = process.env.POLL_SCREENSHOTS || '/workspace/input/poll-screenshots';
const endpoint = 'https://energized-kiwi-650.convex.site/v1/votes';
const key = 'thedailyskim.poll-voter.v1';
const url = 'https://thedailyskim.com/email/thanks.html?poll=tesla-factory-priorities&vote=yes';
const day = 86400000;
(async () => {
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  let cases = 0;
  async function setup(options={}) {
    const context = await browser.newContext({viewport:options.mobile?{width:390,height:844}:{width:1280,height:900}});
    if (options.init) await context.addInitScript(options.init);
    let calls=[];
    await context.route('**/*',async route=>{
      const req=route.request(), u=new URL(req.url());
      if(req.url()===endpoint){
        calls.push({method:req.method(),data:req.postDataJSON(),headers:req.headers()});
        if(options.collector) return options.collector(route,calls.length);
        return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,duplicate:false,vote:'yes'})});
      }
      if(u.origin==='https://thedailyskim.com'){
        let file=path.resolve(root,'.'+decodeURIComponent(u.pathname));
        assert(file.startsWith(root+path.sep));
        return route.fulfill({path:file,contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.ttf')?'font/ttf':'text/html'});
      }
      throw new Error('Unexpected external request: '+req.url());
    });
    const page=await context.newPage();
    await page.goto(options.url||url);
    await page.waitForFunction(()=>document.getElementById('confirm-vote'));
    // Script is deferred and has finished before load. Link visit must not POST.
    assert.equal(calls.length,0);
    return {context,page,calls,close:()=>context.close()};
  }
  async function confirm(s){await s.page.locator('#confirm-vote').click();}
  async function status(s,expected){await s.page.locator('#poll-heading').filter({hasText:expected}).waitFor();}
  async function done(s){cases++;await s.close();}

  let s=await setup();
  assert.equal(await s.page.locator('#confirm-vote').innerText(),'Confirm Yes');
  assert.equal(await s.page.evaluate(k=>localStorage.getItem(k),key),null);
  fs.mkdirSync(out,{recursive:true});
  await s.page.screenshot({path:path.join(out,'desktop-confirm.png'),fullPage:true});
  await confirm(s);await status(s,'Thanks for confirming your vote');
  assert.equal(s.calls.length,1); assert.equal(s.calls[0].method,'POST');
  assert.deepEqual(Object.keys(s.calls[0].data).sort(),['brand','poll','vote','voter']);
  assert.match(s.calls[0].data.voter,/^[a-f0-9]{32}$/);
  assert.equal(s.calls[0].data.brand,'thedailyskim');
  assert.equal(s.calls[0].data.poll,'tesla-factory-priorities');
  assert.equal(s.calls[0].headers['referer'],undefined);
  assert.equal(s.calls[0].headers['cookie'],undefined);
  assert.equal(await s.page.locator('#confirm-vote').isDisabled(),true);
  await s.page.screenshot({path:path.join(out,'desktop-recorded.png'),fullPage:true});
  const identity=s.calls[0].data.voter;
  await s.page.reload();assert.equal(s.calls.length,1);
  await confirm(s);await status(s,'Thanks for confirming your vote');
  assert.equal(s.calls[1].data.voter,identity);
  await done(s);

  s=await setup({mobile:true,collector:r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,duplicate:true,vote:'no'})})});
  await s.page.screenshot({path:path.join(out,'mobile-confirm.png'),fullPage:true});
  await confirm(s);await status(s,'You already answered this poll');
  assert.equal(await s.page.locator('#vote').innerText(),'Recorded: No');
  await s.page.screenshot({path:path.join(out,'mobile-duplicate.png'),fullPage:true});
  await done(s);

  for(const suffix of ['', '?vote=yes','?poll=x','?poll=Bad&vote=yes','?poll=x&vote=maybe',
    '?poll=x&vote=yes&vote=no','?poll=x&poll=y&vote=yes','?poll='+('a'.repeat(101))+'&vote=yes']){
    s=await setup({url:'https://thedailyskim.com/email/thanks.html'+suffix});
    await status(s,'Check your poll link');
    assert.equal(await s.page.locator('#confirm-vote').isVisible(),false);
    assert.equal(s.calls.length,0);await done(s);
  }
  for(const init of [
    ()=>Object.defineProperty(window,'localStorage',{get(){throw Error('blocked');}}),
    ()=>Object.defineProperty(Storage.prototype,'setItem',{value(){throw Error('blocked');}}),
    ()=>localStorage.setItem('thedailyskim.poll-voter.v1','corrupt'),
    ()=>Object.defineProperty(window,'crypto',{value:{}}),
    ()=>localStorage.setItem('thedailyskim.poll-voter.v1',JSON.stringify({id:'x',expires:Date.now()+1000}))
  ]){
    s=await setup({init});await confirm(s);await status(s,'Your vote was not sent');
    assert.equal(s.calls.length,0);
    await s.page.locator('#confirm-vote').evaluate(b=>b.dispatchEvent(new Event('click')));
    assert.equal(s.calls.length,0);
    assert.equal(await s.page.locator('#confirm-vote').isDisabled(),true);
    await done(s);
  }
  // Definitive backend rejections are not uncertain network acknowledgments.
  for(const code of ['poll_closed','unknown_poll','voting_disabled','poll_capacity_reached']){
    s=await setup({collector:r=>r.fulfill({status:code==='unknown_poll'?404:409,contentType:'application/json',body:JSON.stringify({ok:false,error:code})})});
    await confirm(s);
    await status(s,code==='poll_closed'?'This poll is closed':code==='unknown_poll'?'This poll is not available':'Voting is temporarily unavailable');
    assert.match(await s.page.locator('#poll-status').innerText(),/No vote was saved/);
    assert.equal(s.calls.length,1);
    const terminal=code==='poll_closed'||code==='unknown_poll';
    assert.equal(await s.page.locator('#confirm-vote').isDisabled(),terminal);
    assert.equal(await s.page.locator('#vote').innerText(),'Selected: Yes');
    if(terminal){
      await s.page.locator('#confirm-vote').evaluate(b=>b.dispatchEvent(new Event('click')));
      assert.equal(s.calls.length,1);
    } else {
      const nonce=s.calls[0].data.voter;
      await confirm(s);
      await s.page.waitForFunction(()=>!document.getElementById('confirm-vote').disabled);
      assert.equal(s.calls.length,2);
      assert.equal(s.calls[1].data.voter,nonce);
    }
    await done(s);
  }
  // Backend rejection, network failure, malformed success and timeout all retry
  // with the same identity; no optimistic confirmation or fake vote counts.
  for(const kind of ['backend','network','malformed','mismatch','timeout']){
    s=await setup({collector:(r,n)=>{
      if(n>1)return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,duplicate:true,vote:'yes'})});
      if(kind==='network')return r.abort('failed');
      if(kind==='timeout')return new Promise(()=>{});
      return r.fulfill({status:kind==='backend'?503:200,contentType:'application/json',
        body:kind==='malformed'?'{}':JSON.stringify(kind==='mismatch'?{ok:true,duplicate:false,vote:'no'}:{ok:false,error:'internal_error'})});
    }});
    if(kind==='timeout')await s.page.clock.install();
    await confirm(s);
    if(kind==='timeout')await s.page.clock.fastForward(16000);
    await status(s,'Your vote could not be confirmed');
    assert.equal(await s.page.locator('#confirm-vote').isDisabled(),false);
    const nonce=s.calls[0].data.voter;
    await confirm(s);await status(s,'You already answered this poll');
    assert.equal(s.calls[1].data.voter,nonce);
    await done(s);
  }
  let release,arrived;
  const arrival=new Promise(resolve=>{arrived=resolve;});
  s=await setup({collector:r=>new Promise(resolve=>{release=()=>r.fulfill({status:200,contentType:'application/json',body:'{"ok":true,"duplicate":false,"vote":"yes"}'}).then(resolve);arrived();})});
  await s.page.locator('#confirm-vote').evaluate(b=>{b.click();b.click();b.dispatchEvent(new Event('click'));});
  await s.page.waitForFunction(()=>document.getElementById('poll-status').textContent.includes('Sending'));
  assert.equal(await s.page.locator('#confirm-vote').isDisabled(),true);
  await arrival;
  assert.equal(s.calls.length,1);
  await release();await status(s,'Thanks for confirming your vote');await done(s);

  // Expired nonce rotates after 30 days, live nonce remains immutable.
  for(const expired of [false,true]){
    s=await setup();
    await s.page.evaluate(({expired,day,key})=>localStorage.setItem(key,JSON.stringify({id:'a'.repeat(32),expires:Date.now()+(expired?-day:day)})),{expired,day,key});
    await confirm(s);await status(s,'Thanks for confirming your vote');
    assert.equal(s.calls[0].data.voter==='a'.repeat(32),!expired);
    const record=await s.page.evaluate(k=>JSON.parse(localStorage.getItem(k)),key);
    assert(record.expires<=Date.now()+30*day+1000);
    await done(s);
  }
  await browser.close();
  console.log(`PASS ${cases} real Chromium mocked-collector cases. No live collector requests.`);
})().catch(e=>{console.error(e);process.exit(1);});
