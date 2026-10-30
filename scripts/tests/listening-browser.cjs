/* Controlled browser acceptance test. No external APIs or microphone hardware. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {voiceCommand,mentionedStory}=require('../../web/lib/listening.ts');
assert.equal(voiceCommand('KUMAIL, repeat that.'),'repeat');assert.equal(voiceCommand('What happened next?'),null);assert.equal(mentionedStory('Explain the third story in more detail'),2);assert.equal(mentionedStory('Play story 2'),1);
function wav(seconds=30){const rate=8000,bytes=rate*seconds*2,buffer=Buffer.alloc(44+bytes);buffer.write('RIFF');buffer.writeUInt32LE(36+bytes,4);buffer.write('WAVEfmt ',8);buffer.writeUInt32LE(16,16);buffer.writeUInt16LE(1,20);buffer.writeUInt16LE(1,22);buffer.writeUInt32LE(rate,24);buffer.writeUInt32LE(rate*2,28);buffer.writeUInt16LE(2,32);buffer.writeUInt16LE(16,34);buffer.write('data',36);buffer.writeUInt32LE(bytes,40);return buffer;}
const sources=[{id:'a',title:'Fixture Oman story',text:'Evidence for the first controlled story.',publisher:'Fixture publisher',url:'https://publisher.example/a'},{id:'b',title:'Fixture technology story',text:'Evidence for the second controlled story.',publisher:'Fixture publisher',url:'https://publisher.example/b'}];
const report={id:'fixture-briefing',title:'Morning Intelligence',text:'FULL ANALYST REPORT SHOULD STAY HIDDEN',ready_at:'2026-10-30T07:10:00+04:00',articles:sources,presentation_version:'spoken-v1',audio_status:'ready',audio_file:'intro.mp3',estimated_duration_seconds:540,narration_method:'Controlled test fixture',headline_summary:'A development in Oman. A technology update.',stories:sources.map(s=>({headline:s.title,summary:'One concise paragraph with the relevant context.',source_ids:[s.id]})),audio_segments:[{audio_file:'intro.mp3',title:'Your briefing',source_ids:[]},{audio_file:'a.mp3',title:sources[0].title,source_ids:['a'],story_index:0},{audio_file:'a-part-two.mp3',title:sources[0].title,source_ids:['a'],story_index:0},{audio_file:'b.mp3',title:sources[1].title,source_ids:['b'],story_index:1},{audio_file:'outro.mp3',title:'The outlook',source_ids:[]}]};
const answer={id:'fixture-answer',question:'Who is responsible for that?',text:'A written answer with evidence.',sources:[sources[1]],ready_at:report.ready_at,presentation_version:'spoken-v1',audio_status:'ready',audio_file:'answer.mp3',audio_segments:[{audio_file:'answer.mp3',title:'Your answer',source_ids:['b']}]};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1440,height:1100}});const page=await context.newPage();const failures=[];page.on('pageerror',e=>failures.push(e.message));
 let audioRequests=0,questionBody=null,releaseAnswer;const gate=new Promise(resolve=>releaseAnswer=resolve);
 await page.addInitScript(()=>{window.__micStarts=0;window.SpeechRecognition=class{start(){window.__micStarts++;window.__mic=this;this.onstart?.();}stop(){this.onend?.();}abort(){this.onend?.();}};});
 const dashboard={briefings:[report],answers:[],sources:[],preferences:{interests:['Oman'],briefing_minutes:{morning:9,midday:4,afternoon:6,evening:9,manual:10}},integrations:{openai:'configured_not_verified',elevenlabs:'configured_not_verified'}};
 await page.route('**/api/**',async route=>{const path=new URL(route.request().url()).pathname;if(path==='/api/dashboard')return route.fulfill({json:dashboard});if(path.startsWith('/api/audio/')){audioRequests++;return route.fulfill({contentType:'audio/wav',body:wav()});}if(path==='/api/questions'){questionBody=route.request().postDataJSON();return route.fulfill({status:202,json:{id:answer.id,conversation_id:'fixture-conversation'}});}if(path.startsWith('/api/answers/')){await gate;return route.fulfill({json:answer});}if(path==='/api/operations')return route.fulfill({json:{workers:[]}});throw Error('Unexpected browser fixture request '+path);});
 try{
  await page.goto(process.env.KUMAIL_TEST_URL||'http://127.0.0.1:3100');
  await page.getByLabel('Private access key').fill('fixture-key-'+'x'.repeat(40));await page.getByRole('button',{name:'Open KUMAIL'}).click();
  await page.getByRole('heading',{name:'Your world. Just listen.'}).waitFor();
  assert.equal(audioRequests,0,'login must not start scheduled playback');assert.equal(await page.evaluate(()=>window.__micStarts),0,'microphone must stay off until requested');
  assert(!await page.locator('body').innerText().then(text=>text.includes('FULL ANALYST REPORT')),'written report stays hidden by default');
  await page.screenshot({path:'/tmp/kumail-listening-desktop.png',fullPage:true});
  await page.getByRole('button',{name:'Play briefing',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('audio').paused);
  await page.getByRole('button',{name:'Next story',exact:true}).click();await page.getByText('Chapter 2 of 5').waitFor();
  await page.getByRole('button',{name:'Next story',exact:true}).click();await page.getByText('Chapter 4 of 5').waitFor();await page.waitForFunction(()=>!document.querySelector('audio').paused);
  await page.evaluate(()=>{document.querySelector('audio').currentTime=7;});
  await page.getByRole('button',{name:'Interrupt & ask',exact:true}).click();assert(await page.evaluate(()=>document.querySelector('audio').paused),'interruption pauses immediately');
  await page.getByLabel('Your question',{exact:true}).fill('Who is responsible for that?');await page.getByRole('button',{name:'Send question',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="Send question"]').disabled);while(!questionBody)await new Promise(r=>setTimeout(r,20));
  assert.equal(questionBody.briefing_id,report.id);assert.equal(questionBody.article_id,'b','question carries the exact current story');assert(await page.evaluate(()=>document.querySelector('audio').paused));
  releaseAnswer();await page.getByText('Your question · Spoken answer',{exact:true}).waitFor();await page.waitForFunction(()=>!document.querySelector('audio').paused);
  await page.getByRole('button',{name:'Resume briefing',exact:true}).click();await page.getByText('Chapter 4 of 5').waitFor();await page.waitForFunction(()=>document.querySelector('audio').currentTime>=7&&!document.querySelector('audio').paused);
  await page.getByRole('button',{name:'Interrupt & ask',exact:true}).click();assert.equal(await page.evaluate(()=>window.__micStarts),2);
  await page.evaluate(()=>window.__mic.onresult({resultIndex:0,results:[{isFinal:true,0:{transcript:'KUMAIL, repeat that.'}}]}));
  await page.waitForFunction(()=>!document.querySelector('audio').paused&&document.querySelector('audio').currentTime<2);await page.getByText('Chapter 4 of 5').waitFor();
  await page.getByRole('button',{name:'Pause',exact:true}).click();const requestsBefore=audioRequests;
  dashboard.briefings.unshift({...report,id:'scheduled-new-edition',title:'Afternoon Intelligence'});
  await page.waitForTimeout(4500);assert.equal(audioRequests,requestsBefore,'new scheduled editions must not autoplay');assert(await page.evaluate(()=>document.querySelector('audio').paused));
  await page.getByRole('button',{name:'Headlines & evidence'}).click();await page.getByRole('dialog',{name:'Headlines and evidence'}).waitFor();assert.equal(await page.getByText('FULL ANALYST REPORT SHOULD STAY HIDDEN',{exact:true}).isVisible(),false);await page.getByText('Full written record',{exact:true}).click();assert(await page.getByText('FULL ANALYST REPORT SHOULD STAY HIDDEN',{exact:true}).isVisible());await page.getByRole('button',{name:'Close evidence'}).click();
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'mobile layout must fit the viewport');await page.screenshot({path:'/tmp/kumail-listening-mobile.png',fullPage:true});
  assert.deepEqual(failures,[],'no client runtime errors');console.log('PASS: user-controlled playback, exact-story interruption, spoken answer, resume position, explicit microphone, voice command, no scheduled autoplay, optional evidence and mobile layout');
 }finally{releaseAnswer();await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
