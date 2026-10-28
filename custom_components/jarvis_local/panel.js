class JarvisLocalPanel extends HTMLElement {
  connectedCallback() { if (!this.root) this.setConfig({}); }
  set panel(panel) { this.setConfig(panel.config || {}); }
  setConfig(config) { this.config = config; if (!this.root) this.build(); this.loadInfo(); }
  set hass(hass) {
    this._hass = hass;
    if (!this.infoLoaded && !this.loadingInfo && this.root) this.loadInfo();
    if (!this.voicePipelines && !this.loadingPipelines && this.root) this.loadVoicePipelines();
    if (this.root) {
      const id=this.config.agent_id || 'conversation.jarvis_local_test';
      const state=hass.states[id];
      const available=!!state && !['unavailable','unknown'].includes(state.state);
      this.root.querySelector('.connection').textContent='v0.20.1';
      this.root.querySelector('.overview-agent').textContent='Agent: '+(available?'Available':'Not available');
      this.updateOverview();
    }
  }
  getCardSize() { return 7; }
  build() {
    this.root = this.attachShadow({mode:'open'});
    this.root.innerHTML = `<style>
:host{display:block;overflow:auto;height:100%;background:var(--primary-background-color);color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,system-ui)}
.toolbar{display:flex;align-items:center;gap:12px;padding:10px 16px;background:var(--app-header-background-color,var(--card-background-color));position:sticky;top:0;z-index:2}.toolbar-title{font-size:20px;font-weight:600}.menu{font-size:24px}.fallback{margin-left:auto}
button,select,input{font:inherit;color:inherit}button{min-height:44px;border:1px solid var(--divider-color);border-radius:10px;padding:9px 14px;background:var(--secondary-background-color);cursor:pointer}button:hover{filter:brightness(1.1)}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--primary-color)}button:disabled{opacity:.5;cursor:default}.menu{border:0;background:transparent;min-width:44px}.toolbar button{padding:8px 12px}.toolbar a{color:inherit}
ha-card{display:block;box-sizing:border-box;max-width:960px;margin:20px auto;padding:24px;border-radius:18px;background:var(--card-background-color)}ha-card[hidden]{display:none}h2{margin:0 0 5px}h3{margin:14px 0 6px;font-size:1rem}small{display:block;color:var(--secondary-text-color);margin:6px 0;font-size:.85rem}.connection{margin:0}.chat-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.status{font-size:.85rem;color:var(--secondary-text-color)}.history{min-height:280px;max-height:54vh;overflow:auto;display:flex;flex-direction:column;gap:8px;padding:18px 0;white-space:pre-wrap}.history:empty:before{content:'How can I assist?';color:var(--secondary-text-color);padding:12px;background:var(--secondary-background-color);border-radius:12px;align-self:flex-start}.line{padding:11px 14px;background:var(--secondary-background-color);border-radius:14px;max-width:85%;overflow-wrap:anywhere}.line.user{align-self:flex-end;background:var(--primary-color);color:var(--text-primary-color,#fff)}form{display:flex;gap:8px;align-items:center}form input{flex:1;min-width:0;border:1px solid var(--divider-color);border-radius:11px;background:var(--secondary-background-color);padding:13px}form .send{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:transparent}.speak{min-width:48px;font-size:1.2rem}.tools{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.quick-commands button{margin:4px}.quick-commands h3{margin:12px 0 4px}details{border-top:1px solid var(--divider-color);padding:12px 0}summary{cursor:pointer;font-weight:600}select{max-width:100%;padding:8px;border:1px solid var(--divider-color);border-radius:8px;background:var(--secondary-background-color)}.overview{display:flex;flex-wrap:wrap;gap:6px 18px;padding:8px 12px;margin-top:12px;background:var(--secondary-background-color);border-radius:10px}.overview small{margin:2px 0}.diag-card{padding:12px;margin:8px 0;background:var(--secondary-background-color);border-radius:10px;overflow-wrap:anywhere}.diag-card p{margin:4px 0}.voice-status{min-height:1.2em}.settings-fields label{display:block}.room-label{display:block;margin:10px 0}@media(max-width:600px){ha-card{margin:10px;padding:16px}.toolbar{gap:8px}.toolbar a{display:none}.toolbar-title{font-size:18px}.history{min-height:220px}form{flex-wrap:wrap}form input{flex:1 1 calc(100% - 70px)}.line{max-width:92%}}
</style><header class="toolbar"><button type="button" class="menu" aria-label="Open Home Assistant menu">☰</button><img src="/jarvis_local/logo.png" alt="" width="36" height="36" style="border-radius:9px"><span class="toolbar-title">Jarvis Local</span><button type="button" class="fallback open-settings">Settings</button><a href="/config">HA settings</a></header>
<ha-card class="settings-card" hidden><h2>Jarvis settings</h2><small>Lights and areas are discovered automatically. Choose optional household entities below.</small><div class="settings-fields"></div><h3>Switches used as lights</h3><small>Switches must be exposed to Assist.</small><div class="switch-fields"></div><div class="tools"><button type="button" class="add-switch">Add switch</button><button type="button" class="save-settings">Save settings</button><button type="button" class="close-settings">Back to chat</button></div><small class="settings-message" role="status"></small></ha-card>
<ha-card class="chat-card"><div class="chat-head"><div><h2>Chat with Jarvis</h2><small class="connection">Connecting to Home Assistant…</small></div><button type="button" class="clear">Clear chat</button></div>
<div class="overview" aria-label="Jarvis overview"><small class="overview-agent">Agent: checking…</small><small class="overview-pipeline">Voice assistant: not selected</small><small class="overview-stt">Speech-to-text: not selected</small></div><div class="history" role="log" aria-live="polite"></div>
<form><input aria-label="Message to Jarvis" placeholder="Ask Jarvis anything" required><button class="speak" type="button" aria-label="Start voice input" title="Speak to Jarvis">🎙</button><button class="send">Send</button><button class="preview" type="button">Preview</button></form><small class="voice-status" role="status"></small><button type="button" class="replay-voice" hidden>Play Jarvis reply</button>
<details class="voice-options"><summary>Voice settings</summary><label>Voice assistant <select class="voice-pipeline" aria-label="Voice assistant"><option value="">Loading assistants…</option></select></label><small>Select an assistant whose conversation agent is Jarvis Local. Tap the microphone again to finish speaking. Voice input uses the assistant's speech-to-text and text-to-speech settings.</small></details>
<details class="quick-section"><summary>Favourites and frequently used</summary><section class="quick-commands" aria-label="Saved and frequently used commands"><h3>Favourites</h3><div class="favourites"></div><h3>Frequently used</h3><div class="frequent"></div><small>Tap a favourite to run it. Frequent commands fill the message box. Commands are stored on this device.</small><button type="button" class="favourite-current">Save typed command as favourite</button><button type="button" class="clear-frequent">Clear frequent commands</button><small class="quick-status" role="status"></small></section></details>
<details><summary>Tools and diagnostics</summary><div class="tools"><button type="button" data-command="help">Help</button><button type="button" data-command="discover lights">Discover lights</button><button type="button" data-command="list zones">Zones</button><button type="button" data-command="which lights are on">Light status</button><button type="button" class="test-suite">Preview checks</button></div><label class="room-label">Chat room <select class="room" aria-label="Chat room"><option value="">No room selected</option></select></label><details><summary>Recent voice and chat requests</summary><div class="tools"><button type="button" class="refresh">Refresh</button><button type="button" class="copy-diag">Copy</button><button type="button" class="clear-diag">Clear</button></div><span class="copy-status" role="status"></span><div class="diagnostic-cards"></div><details><summary>Raw diagnostics</summary><pre class="diagnostics" style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto"></pre></details></details></details></ha-card>`;
    this.root.querySelector('.menu').onclick = () => this.dispatchEvent(new Event('hass-toggle-menu', {bubbles:true, composed:true}));
    this.root.querySelector('.open-settings').onclick=()=>this.openSettings();
    this.root.querySelector('.close-settings').onclick=()=>this.showSettings(false);
    this.root.querySelector('.add-switch').onclick=()=>this.addSwitchRow();
    this.root.querySelector('.save-settings').onclick=()=>this.saveSettings();
    this.root.querySelector('.test-suite').onclick=()=>this.previewChecks();
    this.root.querySelector('.favourite-current').onclick=()=>this.addFavourite();
    this.root.querySelector('.clear-frequent').onclick=()=>{this.commandHistory=[];this.saveQuick();this.renderQuick();};
    this.readQuick();this.renderQuick();
    this.root.querySelector('.refresh').onclick=()=>this.loadInfo();
    this.root.querySelector('.copy-diag').onclick=()=>this.copyDiagnostics();
    this.root.querySelector('.clear-diag').onclick=async()=>{await this._hass.callWS({type:'jarvis_local/clear_diagnostics'});this.loadInfo();};
    this.root.querySelector('form').onsubmit = e => { e.preventDefault(); this.send(); };
    this.root.querySelector('.preview').onclick = () => this.send(true);
    this.root.querySelector('.speak').onclick = () => this.toggleVoice();
    this.root.querySelector('.replay-voice').onclick = () => {if(this.replyAudio)this.replyAudio.play().catch(()=>this.voiceStatus('Audio playback is unavailable on this device.'));};
    this.root.querySelector('.voice-pipeline').onchange = e => {try {localStorage.setItem('jarvis_local_voice_pipeline',e.target.value);} catch (_) {} this.updateOverview(); };
    this.loadVoicePipelines();
    for (const button of this.root.querySelectorAll('[data-command]')) button.onclick = () => {this.root.querySelector('form input').value=button.dataset.command;this.send();};
    this.root.querySelector('.clear').onclick = () => {this.root.querySelector('.history').replaceChildren();this.conversationId=undefined;};
  }
  disconnectedCallback() { this.stopVoice(true); }
  voiceStatus(message) { if(this.root) this.root.querySelector('.voice-status').textContent=message; }
  async loadVoicePipelines() {
    if(!this._hass || !this.root || this.loadingPipelines) return;
    this.loadingPipelines=true;
    const select=this.root.querySelector('.voice-pipeline');
    try {
      const result=await this._hass.callWS({type:'assist_pipeline/pipeline/list'});
      const agent=this.config.agent_id || 'conversation.jarvis_local_test';
      const pipelines=result.pipelines.filter(p=>p.conversation_engine===agent && p.stt_engine);
      let saved='';try {saved=localStorage.getItem('jarvis_local_voice_pipeline') || '';} catch (_) {}
      select.replaceChildren(new Option(pipelines.length?'Choose an assistant':'No Jarvis voice assistant found',''));
      for(const pipeline of pipelines)select.add(new Option(pipeline.name,pipeline.id));
      const preferred=pipelines.find(p=>p.id===saved) || pipelines.find(p=>p.id===result.preferred_pipeline) || (pipelines.length===1?pipelines[0]:null);
      if(preferred)select.value=preferred.id;
      this.voicePipelines=pipelines;this.updateOverview();
    } catch(e) {select.replaceChildren(new Option('Unable to load assistants',''));this.voiceStatus('Could not load voice assistants: '+(e.message || String(e)));}
    finally {this.loadingPipelines=false;}
  }
  updateOverview() {
    if(!this.root)return;
    const select=this.root.querySelector('.voice-pipeline');
    const pipeline=(this.voicePipelines || []).find(p=>p.id===select?.value);
    this.root.querySelector('.overview-pipeline').textContent='Voice assistant: '+(pipeline?.name || 'not selected');
    this.root.querySelector('.overview-stt').textContent='Speech-to-text: '+(pipeline?.stt_engine || 'not selected')+' (configured)';
  }
  async toggleVoice() {
    if(this.voiceSession) {if(this.voiceSession.recording)this.stopVoice(false);return;}
    if(this.busy)return;
    await this.loadVoicePipelines();
    const id=this.root.querySelector('.voice-pipeline').value;
    const pipeline=(this.voicePipelines || []).find(p=>p.id===id);
    if(!pipeline){this.root.querySelector('.voice-options').open=true;this.voiceStatus('Choose a voice assistant configured with Jarvis Local and speech-to-text.');return;}
    if(!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.AudioContext){this.voiceStatus('Microphone needs a secure connection and browser permission.');return;}
    const session={recording:true,buffer:[],handler:null,ready:false,unsub:null,ended:false};
    this.voiceSession=session;this.busy=true;
    const button=this.root.querySelector('.speak');button.textContent='■';button.setAttribute('aria-label','Stop recording');this.voiceStatus('Listening. Tap the microphone again when finished.');
    try {
      session.stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      if(session.ended){session.stream.getTracks().forEach(t=>t.stop());return;}
      session.context=new AudioContext();await session.context.resume();
      if(session.ended){session.context.close();return;}
      session.source=session.context.createMediaStreamSource(session.stream);
      session.node=session.context.createScriptProcessor(4096,1,1);
      session.gain=session.context.createGain();session.gain.gain.value=0;
      session.node.onaudioprocess=e=>{
        if(!session.recording)return;
        const input=e.inputBuffer.getChannelData(0),pcm=new Int16Array(input.length);
        for(let i=0;i<input.length;i++){const x=Math.max(-1,Math.min(1,input[i]));pcm[i]=x<0?x*32768:x*32767;}
        if(session.ready)this.sendVoiceChunk(session,pcm);else session.buffer.push(pcm);
      };
      session.source.connect(session.node);session.node.connect(session.gain);session.gain.connect(session.context.destination);
      session.timer=setTimeout(()=>this.stopVoice(false),30000);
      const options={type:'assist_pipeline/run',start_stage:'stt',end_stage:pipeline.tts_engine?'tts':'intent',input:{sample_rate:session.context.sampleRate},pipeline:id};
      if(this.conversationId)options.conversation_id=this.conversationId;
      const unsubscribe=await this._hass.connection.subscribeMessage(e=>this.voiceEvent(session,e),options);
      if(session.ended)unsubscribe();else session.unsub=unsubscribe;
    } catch(e) {if(!session.ended){this.line('Error','Voice input could not start: '+(e.message || String(e)));this.stopVoice(true);}}
  }
  sendVoiceChunk(session,pcm) {
    if(session.handler===null || session.ended)return;
    const packet=new Uint8Array(1+pcm.byteLength);packet[0]=session.handler;packet.set(new Uint8Array(pcm.buffer,pcm.byteOffset,pcm.byteLength),1);
    try {this._hass.connection.socket.send(packet);} catch(e) {this.line('Error','Voice connection was interrupted.');this.stopVoice(true);}
  }
  voiceEvent(session,event) {
    if(session.ended)return;
    if(event.type==='run-start')session.handler=event.data.runner_data.stt_binary_handler_id;
    else if(event.type==='stt-start'){
      if(session.handler===null){this.line('Error','Voice assistant did not provide an audio channel.');this.stopVoice(true);return;}
      session.ready=true;for(const pcm of session.buffer)this.sendVoiceChunk(session,pcm);session.buffer=[];
      if(!session.recording)this.sendVoiceChunk(session,new Int16Array());
    } else if(event.type==='stt-end'){
      this.stopVoiceCapture(session);this.voiceStatus('Thinking…');
      const text=event.data.stt_output?.text;if(text){session.transcript=text;this.line('You',text);}
    } else if(event.type==='intent-end'){
      const reply=event.data.intent_output;this.conversationId=reply.conversation_id;
      if(event.data.processed_locally===false && reply.response?.speech?.plain?.extra_data?.jarvis_local?.trackable===true && session.transcript)this.trackCommand(session.transcript);
      this.line('Jarvis',reply.response?.speech?.plain?.speech || 'No text response.');
      if(event.data.processed_locally===true)this.line('Routing','Home Assistant processed this request locally. It may have matched a sentence trigger before Jarvis. Check the Assist debug trace.');
    } else if(event.type==='tts-end') {
      const url=event.data.tts_output?.url;
      if(url){if(this.replyAudio)this.replyAudio.pause();this.replyAudio=new Audio(this._hass.hassUrl ? this._hass.hassUrl(url) : url);this.root.querySelector('.replay-voice').hidden=false;this.replyAudio.play().catch(()=>this.voiceStatus('Tap Play Jarvis reply to hear the response.'));}
    } else if(event.type==='error'){this.line('Error',event.data?.message || 'Voice assistant failed.');this.stopVoice(true);}
    else if(event.type==='run-end'){this.stopVoice(true);this.loadInfo();}
  }
  stopVoiceCapture(session) {
    if(!session)return;session.recording=false;clearTimeout(session.timer);
    if(session.node){session.node.onaudioprocess=null;session.node.disconnect();}
    if(session.source)session.source.disconnect();if(session.gain)session.gain.disconnect();
    if(session.stream)session.stream.getTracks().forEach(t=>t.stop());
    if(session.context && session.context.state!=='closed')session.context.close().catch(()=>{});
    if(this.root){const button=this.root.querySelector('.speak');button.textContent='🎙';button.setAttribute('aria-label','Start voice input');}
  }
  stopVoice(cancel) {
    const session=this.voiceSession;if(!session)return;
    this.stopVoiceCapture(session);
    if(!cancel && !session.context){session.ended=true;this.voiceSession=null;this.busy=false;this.voiceStatus('Voice input cancelled.');return;}
    if(!cancel){if(session.ready)this.sendVoiceChunk(session,new Int16Array());this.voiceStatus('Processing…');return;}
    session.ended=true;if(session.unsub)session.unsub();this.voiceSession=null;this.busy=false;if(this.root && this.root.querySelector('.replay-voice').hidden)this.voiceStatus('');
  }
  readQuick() {
    this.favourites=[];this.commandHistory=[];
    try {
      const previous=JSON.parse(localStorage.getItem('jarvis_local_quick_commands_v1') || '{}');
      const saved=localStorage.getItem('jarvis_local_quick_commands_v2');
      const value=saved ? JSON.parse(saved) : {favourites:previous.favourites,history:[]};
      if(Array.isArray(value.favourites))this.favourites=value.favourites.filter(v=>typeof v==='string' && v.length<=150).slice(0,20);
      if(Array.isArray(value.history))this.commandHistory=value.history.filter(v=>v && typeof v.text==='string' && v.text.length<=150 && Number.isFinite(v.count) && v.count>0).slice(0,50);
    } catch(e) {this.quickStorageUnavailable=true;}
  }
  saveQuick() {
    try {localStorage.setItem('jarvis_local_quick_commands_v2',JSON.stringify({favourites:this.favourites,history:this.commandHistory}));this.quickStorageUnavailable=false;}
    catch(e){this.quickStorageUnavailable=true;}
    this.root.querySelector('.quick-status').textContent=this.quickStorageUnavailable?'Unable to save on this device; commands will be lost when the page closes.':'';
  }
  addFavourite() {
    const value=this.root.querySelector('form input').value.trim();
    if(!value || value.length>150){this.root.querySelector('.quick-status').textContent='Type a command of up to 150 characters first.';return;}
    if(this.favourites.some(x=>x.toLowerCase()===value.toLowerCase())){this.root.querySelector('.quick-status').textContent='That command is already a favourite.';return;}
    if(this.favourites.length>=20){this.root.querySelector('.quick-status').textContent='Remove a favourite before adding another.';return;}
    this.favourites.push(value);this.saveQuick();this.renderQuick();
  }
  trackCommand(value) {
    if(!value || value.length>150 || /^(?:preview|dry run|what would you do if i said)\b/i.test(value))return;
    const old=this.commandHistory.find(x=>x.text.toLowerCase()===value.toLowerCase());
    if(old)old.count=Math.min(old.count+1,1000000);else this.commandHistory.push({text:value,count:1});
    this.commandHistory.sort((a,b)=>b.count-a.count);this.commandHistory=this.commandHistory.slice(0,50);this.saveQuick();this.renderQuick();
  }
  renderQuick() {
    const fav=this.root.querySelector('.favourites'),freq=this.root.querySelector('.frequent');fav.replaceChildren();freq.replaceChildren();
    const make=(text,container,removable)=>{
      const wrapper=document.createElement('span');
      const button=document.createElement('button');button.type='button';button.textContent=text;button.title='Put this command in the message box';
      button.onclick=()=>{const input=this.root.querySelector('form input');input.value=text;if(removable)this.send();else input.focus();};button.title=removable?'Run this command':'Put this command in the message box';if(removable)button.setAttribute('aria-label','Run favourite '+text);wrapper.append(button);
      if(removable){const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','Remove favourite '+text);remove.onclick=()=>{this.favourites=this.favourites.filter(x=>x!==text);this.saveQuick();this.renderQuick();};wrapper.append(remove);}
      container.append(wrapper);
    };
    for(const value of this.favourites)make(value,fav,true);
    if(!this.favourites.length)fav.textContent='No favourites yet.';
    const frequent=this.commandHistory.filter(x=>!this.favourites.some(f=>f.toLowerCase()===x.text.toLowerCase())).slice(0,5);
    for(const item of frequent)make(item.text,freq,false);
    if(!frequent.length)freq.textContent='Your frequently used chat commands will appear here.';
  }
  async copyDiagnostics() {
    const text=this.root.querySelector('.diagnostics').textContent;
    const status=this.root.querySelector('.copy-status');
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(text);
      status.textContent='Copied.';
    } catch (error) {
      const pre=this.root.querySelector('.diagnostics');
      const range=document.createRange();range.selectNodeContents(pre);
      const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
      status.textContent='Select and copy the highlighted diagnostics.';
    }
  }
  showSettings(open) {
    this.root.querySelector('.settings-card').hidden=!open;
    this.root.querySelector('.chat-card').hidden=open;
  }
  entitySelect(domain, value, emptyLabel='Not configured') {
    const select=document.createElement('select');
    select.add(new Option(emptyLabel,''));
    const states=Object.values(this._hass.states).filter(s=>s.entity_id.startsWith(domain+'.')).sort((a,b)=>(a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id));
    for(const state of states) select.add(new Option((state.attributes.friendly_name || state.entity_id)+' ('+state.entity_id+')',state.entity_id));
    if(value && !states.some(s=>s.entity_id===value)) select.add(new Option('Missing: '+value,value));
    select.value=value || '';
    return select;
  }
  async openSettings() {
    if(!this._hass)return;
    await this.loadInfo();
    const fields=[['thermostat','Thermostat','climate'],['car_cable_sensor','Car charging cable sensor','binary_sensor'],['car_battery_sensor','Car battery sensor','sensor'],['guest_mode','Guest mode helper','input_boolean'],['guest_names','Guest names helper','input_text'],['music_script','Music control script','script'],['personality_script','Personality script','script'],['phonetic_script','Phonetic dictionary script','script']];
    const container=this.root.querySelector('.settings-fields');container.replaceChildren();
    for(const [key,label,domain] of fields) {
      const wrap=document.createElement('label');wrap.style.cssText='display:block;margin:12px 0';
      wrap.append(document.createTextNode(label+' '));
      const select=this.entitySelect(domain,this.settings?.[key],key==='thermostat'?'Automatic if one thermostat':'Not configured');
      select.dataset.key=key;select.style.cssText='display:block;max-width:100%;width:100%;padding:10px';wrap.append(select);container.append(wrap);
    }
    this.root.querySelector('.switch-fields').replaceChildren();
    for(const [name,id] of Object.entries(this.settings?.switch_lights || {}))this.addSwitchRow(name,id);
    this.root.querySelector('.settings-message').textContent='';this.showSettings(true);
  }
  addSwitchRow(name='',id='') {
    const row=document.createElement('div');row.style.cssText='display:flex;flex-wrap:wrap;gap:8px;margin:8px 0';
    const input=document.createElement('input');input.placeholder='Spoken name';input.setAttribute('aria-label','Spoken name');input.value=name;input.className='switch-name';
    const select=this.entitySelect('switch',id,'Choose a switch');select.className='switch-entity';select.setAttribute('aria-label','Switch entity');
    const remove=document.createElement('button');remove.type='button';remove.textContent='Remove';remove.onclick=()=>row.remove();
    row.append(input,select,remove);this.root.querySelector('.switch-fields').append(row);
  }
  async saveSettings() {
    const data={switch_lights:{}};
    for(const select of this.root.querySelectorAll('.settings-fields select'))data[select.dataset.key]=select.value;
    for(const row of this.root.querySelectorAll('.switch-fields > div')) {
      const name=row.querySelector('.switch-name').value.trim().toLowerCase().replace(/\s+/g,' '), entity=row.querySelector('.switch-entity').value;
      if(!name || !entity || Object.hasOwn(data.switch_lights,name)){this.root.querySelector('.settings-message').textContent='Each switch needs a unique spoken name and a selected entity.';return;}
      data.switch_lights[name]=entity;
    }
    const button=this.root.querySelector('.save-settings');button.disabled=true;
    try {await this._hass.callWS({type:'jarvis_local/save_settings',settings:data});this.settings=data;this.root.querySelector('.settings-message').textContent='Settings saved. Changes are active now.';}
    catch(e){this.root.querySelector('.settings-message').textContent='Could not save settings: '+(e.message || String(e));}
    finally{button.disabled=false;}
  }
  async previewChecks() {
    if(this.busy || !this._hass)return;
    this.busy=true;
    const room=this.root.querySelector('.room').value;
    const checks=['preview turn the lamp and fairy lights on','preview kitchen spotlights on','preview dining room on'];
    this.line('Checks','Running previews only. A bedroom room selection is required for the lamp example.');
    try {
      for(const text of checks) {
        const request={type:'jarvis_local/process',text};if(room)request.area_id=room;
        const reply=await this._hass.callWS(request);
        this.line(text,reply.response?.speech?.plain?.speech || 'No response');
      }
    } catch(e) {this.line('Checks error',e.message || String(e));}
    finally {this.busy=false;this.loadInfo();}
  }
  async loadInfo() {
    if (!this._hass || !this.root || this.loadingInfo) return;
    this.loadingInfo=true;
    try {
      const data=await this._hass.callWS({type:'jarvis_local/info'});
      const select=this.root.querySelector('.room'),selected=select.value;
      select.replaceChildren(new Option('No room selected',''));
      for(const area of data.areas) select.add(new Option(area.name,area.id));
      select.value=selected;
      this.root.querySelector('.diagnostics').textContent=JSON.stringify(data.diagnostics,null,2);
      this.renderDiagnostics(data.diagnostics || []);
      this.settings=data.settings || {};
      this.infoLoaded=true;
    } catch(e) {this.root.querySelector('.diagnostics').textContent=e.message || String(e);}
    finally {this.loadingInfo=false;}
  }
  renderDiagnostics(records) {
    const container=this.root.querySelector('.diagnostic-cards');container.replaceChildren();
    if(!records.length){container.textContent='No Jarvis requests recorded yet.';return;}
    for(const record of records.slice().reverse()){
      const card=document.createElement('div');card.className='diag-card';
      const fields=[['When',record.time],['Heard',record.received_text],['Understood',record.resolved_text || record.received_text],['Actions',(record.steps || []).map(step=>step.label || step.kind).join('; ') || 'None'],['Result',record.outcome],['Speaker',record.speaker_personalized?'Profile used':'No profile used'],['Reply',record.response]];
      for(const [label,value] of fields){const row=document.createElement('p');row.textContent=label+': '+(value || '—');card.append(row);}container.append(card);
    }
  }
  line(who, text) {const el=document.createElement('div');el.className='line'+(who==='You'?' user':'');el.textContent=who+': '+text;const box=this.root.querySelector('.history');box.append(el);box.scrollTop=box.scrollHeight;}
  async send(preview=false) {
    if(this.busy)return;
    const input=this.root.querySelector('form input');const original=input.value.trim();if(!original)return;const text=(preview ? 'preview ' : '')+original;
    const agent=this.config.agent_id || 'conversation.jarvis_local_test';
    if(!this._hass?.states[agent] || this._hass.states[agent].state==='unavailable'){this.line('Status','Jarvis Local is not loaded. Check the integration startup logs. No command was sent.');return;}
    this.busy=true;this.root.querySelector('.send').disabled=true;input.value='';this.line('You',text);
    const start=performance.now();
    try {const request={type:'jarvis_local/process',text};const room=this.root.querySelector('.room').value;if(room)request.area_id=room;if(this.conversationId)request.conversation_id=this.conversationId;const reply=await this._hass.callWS(request);if(!preview && reply.response?.speech?.plain?.extra_data?.jarvis_local?.trackable===true)this.trackCommand(original);this.conversationId=reply.conversation_id;this.line('Jarvis',reply.response?.speech?.plain?.speech || '(No text reply. The routine may announce through the Bedroom Muse.)');}
    catch(e){this.line('Error',e.message || String(e));}
    finally{this.loadInfo();this.busy=false;this.root.querySelector('.send').disabled=false;input.focus();}
  }
}
if (!customElements.get('jarvis-local-panel')) customElements.define('jarvis-local-panel',JarvisLocalPanel);
