const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
let Panel;
class Element {
  constructor(){this.children=[];this.textContent='';this.value='';this.disabled=false;this.hidden=true;this.style={};}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;}
  setAttribute(name,value){this[name]=value;}
  pause(){}
  play(){return Promise.resolve();}
  set innerHTML(_){throw new Error('Untrusted cache text must not use HTML');}
}
let revoked=[];
const context={HTMLElement:class{},customElements:{get:()=>false,define:(_,cls)=>Panel=cls},
  document:{createElement:()=>new Element()},console,Uint8Array,Blob,atob,btoa,
  URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:url=>revoked.push(url)}};
vm.runInNewContext(fs.readFileSync('custom_components/jarvis_local/panel.js','utf8'),context);
const panel=new Panel();
const elements={};
for(const name of ['voice-cache-summary','voice-cache-source','phrase-suggestions','voice-cache-entries','phrase-text','phrase-kind','prepare-phrase','phrase-message','phrase-player','clip-import-message','clip-import-preview','clip-pack-info','clip-confirm','import-clips'])elements['.'+name]=new Element();
panel.root={querySelector:key=>elements[key]};
const requests=[];
const data={count:1,bytes:2048,limit_bytes:268435456,free_bytes:50000000000,
  storage_available:true,hits:4,misses:1,skipped_writes:0,enabled:true,phrases_enabled:true,
  directory:'/config/jarvis_voice_cache',entity_id:'tts.jarvis_voice_manager',import_voice_token:'active-voice',
  rooms:['Kitchen','Bedroom'],usage:{last_source:'elevenlabs_phrase_cached',generated_clips:1},
  entries:[{text:'<img src=x onerror=alert(1)>',kind:'clip',bytes:2048,provider:'tts.elevenlabs',voice_id:'declan',key:'a'.repeat(64),extension:'wav'}]};
panel._hass={callWS:async request=>{
  requests.push(request);
  if(request.type==='jarvis_local/voice_cache')return data;
  if(request.type==='jarvis_local/prepare_voice_phrase')return {cached:false};
  if(request.type==='jarvis_local/voice_cache_audio')return {audio:Buffer.from('audio').toString('base64'),extension:'wav'};
  if(request.type==='jarvis_local/import_voice_clips')return {imported:['kitchen.'],existing:[],not_saved:[]};
  throw new Error('Unexpected request');
}};
(async()=>{
  await panel.loadVoiceCache();
  assert.match(elements['.voice-cache-summary'].textContent,/1 recordings/);
  assert.equal(elements['.voice-cache-entries'].children[0].children[0].textContent,data.entries[0].text);
  const room=elements['.phrase-suggestions'].children.find(x=>x.textContent==='Kitchen.');
  room.onclick();
  assert.equal(elements['.phrase-text'].value,'Kitchen.');
  assert.equal(requests.length,1,'Suggestions must not generate paid audio');
  elements['.phrase-kind'].value='clip';await panel.preparePhrase();
  const prepare=requests.find(x=>x.type==='jarvis_local/prepare_voice_phrase');
  assert.equal(prepare.text,'Kitchen.');assert.equal(prepare.kind,'clip');
  assert.equal(elements['.prepare-phrase'].disabled,false);
  await panel.playSavedPhrase(data.entries[0]);await panel.playSavedPhrase(data.entries[0]);
  assert.equal(elements['.phrase-player'].src,'blob:test');assert.deepEqual(revoked,['blob:test']);
  assert.equal(requests.filter(x=>x.type==='jarvis_local/prepare_voice_phrase').length,1,'Playback must never generate');
  assert.equal(panel.clipLabel('master-bedroom.mp3'),'master bedroom.');
  assert.equal(panel.clipLabel('up-stairs.mp3'),'upstairs.');
  const pack={schema:1,type:'jarvis_voice_clips',voice_name:'Declan',clips:[{text:'kitchen.',extension:'mp3',audio:'YXVkaW8='}]};
  await panel.loadClipFiles([{name:'rooms.json',size:200,text:async()=>JSON.stringify(pack)}]);
  assert.equal(panel.pendingClips.length,1);
  assert.equal(elements['.clip-confirm'].checked,false);
  await panel.importClips();assert.equal(requests.filter(x=>x.type==='jarvis_local/import_voice_clips').length,0);
  elements['.clip-confirm'].checked=true;await panel.importClips();
  const imported=requests.find(x=>x.type==='jarvis_local/import_voice_clips');
  assert.equal(imported.voice_token,'active-voice');assert.equal(imported.clips[0].text,'kitchen.');
  assert.equal(elements['.import-clips'].disabled,false);
  assert.equal(requests.filter(x=>x.type==='jarvis_local/prepare_voice_phrase').length,1,'Import must never request TTS');
  await panel.loadClipFiles([{name:'unknown.json',size:20,text:async()=>'{"schema":999}'}]);
  assert.equal(panel.pendingClips.length,0);assert.match(elements['.clip-import-message'].textContent,/Not a Jarvis/);
  panel._hass.callWS=async()=>{throw new Error('Storage unavailable');};
  await panel.preparePhrase();assert.match(elements['.phrase-message'].textContent,/Storage unavailable/);
  assert.equal(elements['.prepare-phrase'].disabled,false);
  await panel.loadVoiceCache();assert.match(elements['.voice-cache-summary'].textContent,/Could not load/);
  console.log('Phrase cache interactions passed.');
})().catch(err=>{console.error(err);process.exitCode=1;});



