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
      this.root.querySelector('.connection').textContent='v0.28.0';
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
ha-card{display:block;box-sizing:border-box;max-width:960px;margin:20px auto;padding:24px;border-radius:18px;background:var(--card-background-color)}ha-card[hidden]{display:none}h2{margin:0 0 5px}h3{margin:14px 0 6px;font-size:1rem}small{display:block;color:var(--secondary-text-color);margin:6px 0;font-size:.85rem}.connection{margin:0}.chat-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.status{font-size:.85rem;color:var(--secondary-text-color)}.history{min-height:280px;max-height:54vh;overflow:auto;display:flex;flex-direction:column;gap:8px;padding:18px 0;white-space:pre-wrap}.history:empty:before{content:'How can I assist?';color:var(--secondary-text-color);padding:12px;background:var(--secondary-background-color);border-radius:12px;align-self:flex-start}.line{padding:11px 14px;background:var(--secondary-background-color);border-radius:14px;max-width:85%;overflow-wrap:anywhere}.line.user{align-self:flex-end;background:var(--primary-color);color:var(--text-primary-color,#fff)}form{display:flex;gap:8px;align-items:center}form input{flex:1;min-width:0;border:1px solid var(--divider-color);border-radius:11px;background:var(--secondary-background-color);padding:13px}form .send{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:transparent}.speak{min-width:48px;font-size:1.2rem}.tools{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.quick-commands button{margin:4px}.favourite-item{display:inline-flex;align-items:center;gap:0;margin:4px;border:1px solid var(--divider-color);border-radius:12px;overflow:hidden;background:var(--secondary-background-color)}.favourite-item button{margin:0;border:0;border-radius:0}.favourite-item .remove-favourite{min-width:44px;padding:8px 12px;border-left:1px solid var(--divider-color);color:var(--secondary-text-color);font-size:1.3rem;line-height:1}.favourite-item .remove-favourite:hover{background:var(--error-color,#db4437);color:white}.message-actions{display:flex;justify-content:flex-end;margin-top:5px}.message-actions button{min-height:32px;padding:3px 10px;font-size:.8rem;background:transparent;color:inherit;border-color:currentColor}.message-actions[hidden]{display:none}.quick-commands h3{margin:12px 0 4px}details{border-top:1px solid var(--divider-color);padding:12px 0}summary{cursor:pointer;font-weight:600}select{max-width:100%;padding:8px;border:1px solid var(--divider-color);border-radius:8px;background:var(--secondary-background-color)}.overview{display:flex;flex-wrap:wrap;gap:6px 18px;padding:8px 12px;margin-top:12px;background:var(--secondary-background-color);border-radius:10px}.overview small{margin:2px 0}.diag-card{padding:12px;margin:8px 0;background:var(--secondary-background-color);border-radius:10px;overflow-wrap:anywhere}.diag-card p{margin:4px 0}.voice-status{min-height:1.2em}.settings-fields label{display:block}.room-label{display:block;margin:10px 0}@media(max-width:600px){ha-card{margin:10px;padding:16px}.toolbar{gap:8px}.toolbar a{display:none}.toolbar-title{font-size:18px}.history{min-height:220px}form{flex-wrap:wrap}form input{flex:1 1 calc(100% - 70px)}.line{max-width:92%}}
</style><header class="toolbar"><button type="button" class="menu" aria-label="Open Home Assistant menu">☰</button><img src="/jarvis_local/logo.png" alt="" width="36" height="36" style="border-radius:9px"><span class="toolbar-title">Jarvis Local</span><button type="button" class="fallback open-settings">Settings</button><a href="/config">HA settings</a></header>
<ha-card class="settings-card" hidden><h2>Jarvis settings</h2><small>Lights and areas are discovered automatically. Choose optional household entities below.</small><div class="settings-fields"></div><h3>Voice profiles</h3><small>Use the enrolled name from VoicePipeline as the speaker key. Scores below the threshold get a neutral greeting. One morning response per line; {name} inserts the display name. Voice matching does not grant access.</small><div class="profile-fields"></div><div class="tools"><button type="button" class="add-profile">Add voice profile</button><button type="button" class="save-profiles">Save voice profiles</button></div><small class="profile-message" role="status"></small><h3>Switches used as lights</h3><small>Switches must be exposed to Assist.</small><div class="switch-fields"></div><div class="tools"><button type="button" class="add-switch">Add switch</button><button type="button" class="save-settings">Save settings</button><button type="button" class="close-settings">Back to chat</button></div><small class="settings-message" role="status"></small></ha-card>
<ha-card class="chat-card"><div class="chat-head"><div><h2>Chat with Jarvis</h2><small class="connection">Connecting to Home Assistant…</small></div><button type="button" class="clear">Clear chat</button></div>
<div class="overview" aria-label="Jarvis overview"><small class="overview-agent">Agent: checking…</small><small class="overview-pipeline">Voice assistant: not selected</small><small class="overview-stt">Speech-to-text: not selected</small><button type="button" class="check-bridge">Check bridge connection</button><small class="bridge-status" role="status"></small></div><div class="history" role="log" aria-live="polite"></div>
<form><input aria-label="Message to Jarvis" placeholder="Ask Jarvis anything" required><button class="speak" type="button" aria-label="Start voice input" title="Speak to Jarvis">🎙</button><button class="send">Send</button><button class="preview" type="button">Preview</button></form><small class="voice-status" role="status"></small><button type="button" class="replay-voice" hidden>Play Jarvis reply</button>
<details class="voice-options"><summary>Voice settings</summary><label>Voice assistant <select class="voice-pipeline" aria-label="Voice assistant"><option value="">Loading assistants…</option></select></label><small>Select an assistant whose conversation agent is Jarvis Local. Tap the microphone again to finish speaking. Voice input uses the assistant's speech-to-text and text-to-speech settings.</small></details>
<details class="voice-cache-section"><summary>Voice cache</summary>
<small>Saved speech stays in Home Assistant. Prepare reusable clips or a whole sentence for more natural speech. Preparing missing audio uses your configured ElevenLabs provider and may use credits.</small>
<div class="tools"><button type="button" class="refresh-voice-cache">Refresh voice cache</button></div>
<p class="voice-cache-summary" role="status">Open to load saved speech.</p><small class="voice-cache-source"></small>
<label>Phrase <input class="phrase-text" aria-label="Phrase to save" maxlength="200" placeholder="country"></label>
<label>Save as <select class="phrase-kind" aria-label="Phrase type"><option value="clip">Reusable clip</option><option value="sentence">Whole sentence</option></select></label>
<button type="button" class="prepare-phrase">Prepare and save phrase</button>
<small>Room clips end with a full stop to finish the sentence. Clips are prepared only when you press the button.</small>
<div class="tools phrase-suggestions" aria-label="Suggested genres and rooms"></div>
<small class="phrase-message" role="status"></small><audio class="phrase-player" controls hidden aria-label="Saved phrase preview"></audio>
<div class="voice-cache-entries"></div></details>
<details class="quick-section"><summary>Favourites and frequently used</summary><section class="quick-commands" aria-label="Saved and frequently used commands"><h3>Favourites</h3><div class="favourites"></div><h3>Frequently used</h3><div class="frequent"></div><small>Tap a favourite to run it. Frequent commands fill the message box. Commands are stored on this device.</small><button type="button" class="favourite-current">Save typed command as favourite</button><button type="button" class="clear-frequent">Clear frequent commands</button><small class="quick-status" role="status"></small></section></details>
<details><summary>Tools</summary><div class="tools"><button type="button" data-command="help">Help</button><button type="button" data-command="discover lights">Discover lights</button><button type="button" data-command="list zones">Zones</button><button type="button" data-command="which lights are on">Light status</button></div><label class="room-label">Chat room <select class="room" aria-label="Chat room"><option value="">No room selected</option></select></label><details><summary>Troubleshooting</summary><label><input type="checkbox" class="debug-toggle"> Enable debug and troubleshooting</label><small>Off by default. When enabled, recent request details are held temporarily in memory and routing messages are shown in chat. Disabling clears them.</small><div class="debug-content" hidden><button type="button" class="test-suite">Preview checks</button><div class="tools"><button type="button" class="refresh">Refresh</button><button type="button" class="copy-diag">Copy</button><button type="button" class="clear-diag">Clear</button></div><span class="copy-status" role="status"></span><div class="diagnostic-cards"></div><details><summary>Raw diagnostics</summary><pre class="diagnostics" style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto"></pre></details></div></details></details></ha-card>`;
    this.root.querySelector('.menu').onclick = () => this.dispatchEvent(new Event('hass-toggle-menu', {bubbles:true, composed:true}));
    this.root.querySelector('.open-settings').onclick=()=>this.openSettings();
    this.root.querySelector('.close-settings').onclick=()=>this.showSettings(false);
    this.root.querySelector('.add-switch').onclick=()=>this.addSwitchRow();
    this.root.querySelector('.save-settings').onclick=()=>this.saveSettings();
    this.root.querySelector('.add-profile').onclick=()=>this.addProfileRow();
    this.root.querySelector('.save-profiles').onclick=()=>this.saveProfiles();
    this.root.querySelector('.voice-cache-section').ontoggle=e=>{if(e.target.open)this.loadVoiceCache();};
    this.root.querySelector('.refresh-voice-cache').onclick=()=>this.loadVoiceCache();
    this.root.querySelector('.prepare-phrase').onclick=()=>this.preparePhrase();
    this.root.querySelector('.check-bridge').onclick=()=>this.checkBridge();
    this.root.querySelector('.test-suite').onclick=()=>this.previewChecks();
    this.root.querySelector('.debug-toggle').onchange=e=>this.setDebug(e.target.checked);
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
  disconnectedCallback() {
    this.stopVoice(true);
    if(this.phraseUrl){URL.revokeObjectURL(this.phraseUrl);this.phraseUrl=null;}
    const player=this.root?.querySelector('.phrase-player');if(player)player.pause();
  }
  async loadVoiceCache() {
    if(!this._hass || this.loadingVoiceCache)return;
    this.loadingVoiceCache=true;
    const summary=this.root.querySelector('.voice-cache-summary');
    try {
      const data=await this._hass.callWS({type:'jarvis_local/voice_cache'});
      this.voiceCacheData=data;
      const mb=n=>(n/1048576).toFixed(1);
      summary.textContent=data.count+' recordings · '+mb(data.bytes)+' MB of '+mb(data.limit_bytes)+' MB limit · '+(data.free_bytes/1073741824).toFixed(1)+' GB free on Home Assistant storage.';
      const sourceNames={elevenlabs_cached:'Saved whole sentence',elevenlabs_generated:'Whole sentence requested from provider',elevenlabs_phrase_cached:'Reused saved clips or assembled response',elevenlabs_phrase_generated:'Generated missing clips',elevenlabs_category_cached:'Saved alternative response',xtts_cached:'Saved fallback voice',xtts_generated:'Fallback voice generated'};
      this.root.querySelector('.voice-cache-source').textContent='Latest Voice Manager request: '+(sourceNames[data.usage?.last_source] || 'None since restart')+'. '+(data.usage?.generated_clips || 0)+' new clips this session. Cache '+(data.enabled?'enabled':'disabled')+'; phrase assembly '+(data.phrases_enabled?'enabled':'disabled')+'. Use '+data.entity_id+' in your voice assistant. Stored at '+data.directory+'. Counters reset on restart; Home Assistant may also serve audio from its own cache. '+(!data.storage_available?'Storage limit reached; new audio will not be saved. ':'')+(data.skipped_writes?data.skipped_writes+' writes skipped to protect storage.':'');
      const suggestions=this.root.querySelector('.phrase-suggestions');suggestions.replaceChildren();
      for(const text of ['Playing','music from Spotify in the','I requested','in','country','pop','rock','jazz',...(data.rooms || []).map(room=>room+'.')]) {
        const button=document.createElement('button');button.type='button';button.textContent=text;
        button.onclick=()=>{this.root.querySelector('.phrase-text').value=text;this.root.querySelector('.phrase-kind').value='clip';};suggestions.append(button);
      }
      const entries=this.root.querySelector('.voice-cache-entries');entries.replaceChildren();
      if(!data.count){const p=document.createElement('p');p.textContent='No saved recordings yet. Prepare a phrase or use Jarvis Voice Manager.';entries.append(p);}
      for(const entry of data.entries || []) {
        const row=document.createElement('div');row.className='diag-card';
        const title=document.createElement('p');title.textContent=entry.text;
        const detail=document.createElement('small');detail.textContent=(entry.kind || 'sentence')+' · '+(entry.bytes/1024).toFixed(1)+' KB · '+(entry.provider || 'older recording')+' · '+(entry.voice_id || 'voice unavailable');
        const play=document.createElement('button');play.type='button';play.textContent='Play';play.setAttribute('aria-label','Play '+entry.text);play.onclick=()=>this.playSavedPhrase(entry);
        row.append(title,detail,play);entries.append(row);
      }
      if(data.count>(data.entries || []).length){const p=document.createElement('small');p.textContent='Showing the newest '+data.entries.length+' recordings.';entries.append(p);}
    } catch(e){summary.textContent='Could not load voice cache: '+(e.message || String(e));}
    finally{this.loadingVoiceCache=false;}
  }
  async preparePhrase() {
    const button=this.root.querySelector('.prepare-phrase');if(button.disabled)return;
    const text=this.root.querySelector('.phrase-text').value.trim();
    const status=this.root.querySelector('.phrase-message');
    if(!text){status.textContent='Enter a phrase first.';return;}
    button.disabled=true;status.textContent='Preparing speech…';
    try {
      const result=await this._hass.callWS({type:'jarvis_local/prepare_voice_phrase',text,kind:this.root.querySelector('.phrase-kind').value});
      status.textContent=result.saved===false?'Audio was prepared but storage filled up before it could be saved.':result.cached?'That phrase was already saved.':'Phrase prepared. Check the recordings below to preview it.';
      await this.loadVoiceCache();
    } catch(e){status.textContent='Could not prepare phrase: '+(e.message || String(e));}
    finally{button.disabled=false;}
  }
  async playSavedPhrase(entry) {
    const status=this.root.querySelector('.phrase-message');
    try {
      const result=await this._hass.callWS({type:'jarvis_local/voice_cache_audio',key:entry.key,extension:entry.extension});
      const mime={wav:'audio/wav',mp3:'audio/mpeg',ogg:'audio/ogg',flac:'audio/flac'}[result.extension];
      if(!mime)throw new Error('Unsupported recording format');
      const bytes=Uint8Array.from(atob(result.audio),c=>c.charCodeAt(0));
      const player=this.root.querySelector('.phrase-player');player.pause();
      if(this.phraseUrl)URL.revokeObjectURL(this.phraseUrl);
      this.phraseUrl=URL.createObjectURL(new Blob([bytes],{type:mime}));
      player.src=this.phraseUrl;player.hidden=false;await player.play();status.textContent='Playing saved audio on this device.';
    } catch(e){status.textContent='Could not play saved phrase: '+(e.message || String(e));}
  }
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
    const engine=pipeline?.stt_engine;
    const friendly=engine==='stt.jarvis_voice_bridge_test'?'Jarvis Voice Bridge':this._hass?.states?.[engine]?.attributes?.friendly_name;
    this.root.querySelector('.overview-stt').textContent=engine?'Speech-to-text: '+(friendly || engine.replace(/^stt\./,'').replace(/_/g,' '))+' (configured)':'Speech-to-text: not selected';
  }
  async checkBridge() {
    const status=this.root.querySelector('.bridge-status'),button=this.root.querySelector('.check-bridge');
    button.disabled=true;status.textContent='Checking connection…';
    try {
      const result=await this._hass.callWS({type:'jarvis_local/check_voice_bridge'});
      status.textContent=result.bridges.length?result.bridges.map(b=>b.name+': '+(b.reachable?'TCP reachable':'not reachable')).join('; ')+' . This checks the connection only.':'No Jarvis Voice Bridge integration configured.';
    } catch(e){status.textContent='Unable to check the bridge: '+(e.message || String(e));}
    finally{button.disabled=false;}
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
      if(this.debugEnabled && event.data.processed_locally===true)this.line('Routing','Home Assistant processed this request locally. It may have matched a sentence trigger before Jarvis. Check the Assist debug trace.');
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
  addFavourite(text) {
    const value=(typeof text==='string'?text:this.root.querySelector('form input').value).trim();
    if(!value || value.length>150){this.root.querySelector('.quick-status').textContent='Type a command of up to 150 characters first.';return;}
    if(this.favourites.some(x=>x.toLowerCase()===value.toLowerCase())){this.root.querySelector('.quick-status').textContent='That command is already a favourite.';return;}
    if(this.favourites.length>=20){this.root.querySelector('.quick-status').textContent='Remove a favourite before adding another.';return;}
    this.favourites.push(value);this.saveQuick();this.renderQuick();if(!this.quickStorageUnavailable)this.root.querySelector('.quick-status').textContent='Saved favourite: '+value;
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
      const wrapper=document.createElement('span');if(removable)wrapper.className='favourite-item';
      const button=document.createElement('button');button.type='button';button.textContent=text;button.title='Put this command in the message box';
      button.onclick=()=>{const input=this.root.querySelector('form input');input.value=text;if(removable)this.send();else input.focus();};button.title=removable?'Run this command':'Put this command in the message box';if(removable)button.setAttribute('aria-label','Run favourite '+text);wrapper.append(button);
      if(removable){const remove=document.createElement('button');remove.type='button';remove.className='remove-favourite';remove.textContent='×';remove.title='Remove favourite';remove.setAttribute('aria-label','Remove favourite '+text);remove.onclick=()=>{if(!window.confirm('Remove “'+text+'” from favourites?'))return;this.favourites=this.favourites.filter(x=>x!==text);this.saveQuick();this.renderQuick();};wrapper.append(remove);}
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
    const fields=[['weather','Weather entity','weather'],['thermostat','Thermostat','climate'],['car_cable_sensor','Car charging cable sensor','binary_sensor'],['car_battery_sensor','Car battery sensor','sensor'],['guest_mode','Guest mode helper','input_boolean'],['guest_names','Guest names helper','input_text'],['music_script','Music control script','script'],['personality_script','Personality script','script'],['phonetic_script','Phonetic dictionary script','script']];
    const container=this.root.querySelector('.settings-fields');container.replaceChildren();
    for(const [key,label,domain] of fields) {
      const wrap=document.createElement('label');wrap.style.cssText='display:block;margin:12px 0';
      wrap.append(document.createTextNode(label+' '));
      const select=this.entitySelect(domain,this.settings?.[key],key==='thermostat'?'Automatic if one thermostat':'Not configured');
      select.dataset.key=key;select.style.cssText='display:block;max-width:100%;width:100%;padding:10px';wrap.append(select);container.append(wrap);
    }
    this.root.querySelector('.profile-fields').replaceChildren();
    for(const [key,profile] of Object.entries(this.voiceProfiles || {}))this.addProfileRow(key,profile);
    this.root.querySelector('.profile-message').textContent='';
    this.root.querySelector('.switch-fields').replaceChildren();
    for(const [name,id] of Object.entries(this.settings?.switch_lights || {}))this.addSwitchRow(name,id);
    this.root.querySelector('.settings-message').textContent='';this.showSettings(true);
  }
  addProfileRow(key='', profile={}) {
    const row=document.createElement('div');row.className='profile-row';row.style.cssText='padding:14px;margin:12px 0;background:var(--secondary-background-color);border-radius:10px';
    const make=(label,cls,value,type='text')=>{const wrap=document.createElement('label');wrap.textContent=label;wrap.style.cssText='display:block;margin:8px 0';const field=document.createElement('input');field.type=type;field.className=cls;field.value=value;field.style.cssText='display:block;box-sizing:border-box;width:100%;padding:10px';wrap.append(field);row.append(wrap);return field;};
    make('Enrolled speaker key','profile-key',key);make('Display name','profile-name',profile.name || '');
    const threshold=make('Minimum confidence (0 to 1)','profile-threshold',profile.min_confidence ?? 0.75,'number');threshold.min='0';threshold.max='1';threshold.step='0.01';
    const wrap=document.createElement('label');wrap.textContent='Morning responses (one per line)';wrap.style.cssText='display:block;margin:8px 0';const area=document.createElement('textarea');area.className='profile-responses';area.value=(profile.morning_responses || []).join('\n');area.rows=3;area.style.cssText='display:block;box-sizing:border-box;width:100%;padding:10px';wrap.append(area);row.append(wrap);
    const preview=document.createElement('button');preview.type='button';preview.textContent='Preview greeting';preview.onclick=()=>{const lines=area.value.split('\n').map(x=>x.trim()).filter(Boolean);const name=row.querySelector('.profile-name').value.trim();this.root.querySelector('.profile-message').textContent=lines.length?lines[0].replaceAll('{name}',name):'Good morning'+(name?', '+name:'')+'. The morning routine is underway.';};row.append(preview);
    const remove=document.createElement('button');remove.type='button';remove.textContent='Remove profile';remove.onclick=()=>{if(window.confirm('Remove this voice profile from Jarvis? VoicePipeline enrollment is not affected.'))row.remove();};row.append(remove);
    this.root.querySelector('.profile-fields').append(row);
  }
  async saveProfiles() {
    const profiles={};
    for(const row of this.root.querySelectorAll('.profile-row')){
      const key=row.querySelector('.profile-key').value.trim().toLowerCase();
      const threshold=row.querySelector('.profile-threshold').value;
      if(!key || Object.hasOwn(profiles,key) || threshold===''){this.root.querySelector('.profile-message').textContent='Enter a unique speaker key and a confidence value for every profile.';return;}
      profiles[key]={name:row.querySelector('.profile-name').value.trim(),min_confidence:Number(threshold),morning_responses:row.querySelector('.profile-responses').value.split('\n').map(x=>x.trim()).filter(Boolean)};
    }
    const button=this.root.querySelector('.save-profiles');button.disabled=true;
    try {const reply=await this._hass.callWS({type:'jarvis_local/save_voice_profiles',profiles});this.voiceProfiles=reply.profiles;this.root.querySelector('.profile-message').textContent='Voice profiles saved and active.';}
    catch(e){this.root.querySelector('.profile-message').textContent='Could not save profiles: '+(e.message || String(e));}
    finally{button.disabled=false;}
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
      this.debugEnabled=data.debug_enabled===true;
      this.root.querySelector('.debug-toggle').checked=this.debugEnabled;
      this.root.querySelector('.debug-content').hidden=!this.debugEnabled;
      this.root.querySelector('.diagnostics').textContent=JSON.stringify(data.diagnostics,null,2);
      this.renderDiagnostics(data.diagnostics || []);
      this.settings=data.settings || {};this.voiceProfiles=data.voice_profiles || {};
      this.infoLoaded=true;
    } catch(e) {this.root.querySelector('.diagnostics').textContent=e.message || String(e);}
    finally {this.loadingInfo=false;}
  }
  async setDebug(enabled) {
    const toggle=this.root.querySelector('.debug-toggle');toggle.disabled=true;
    try {const result=await this._hass.callWS({type:'jarvis_local/set_debug',enabled});this.debugEnabled=result.enabled===true;this.root.querySelector('.debug-content').hidden=!this.debugEnabled;if(!this.debugEnabled){this.root.querySelector('.diagnostics').textContent='[]';this.renderDiagnostics([]);for(const item of this.root.querySelectorAll('.routing-message'))item.remove();}await this.loadInfo();}
    catch(e){toggle.checked=!!this.debugEnabled;this.voiceStatus('Could not change troubleshooting: '+(e.message || String(e)));}
    finally{toggle.disabled=false;}
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
  line(who, text) {
    const el=document.createElement('div');el.className='line'+(who==='You'?' user':who==='Routing'?' routing-message':'');
    const label=document.createElement('span');label.textContent=who+': '+text;el.append(label);
    if(who==='You'){
      const actions=document.createElement('div');actions.className='message-actions';
      const save=document.createElement('button');save.type='button';save.textContent='☆ Add to favourites';save.setAttribute('aria-label','Add this message to favourites');
      save.onclick=()=>{this.addFavourite(text);this.root.querySelector('.quick-section').open=true;};actions.append(save);el.append(actions);
      el.addEventListener('contextmenu',event=>{event.preventDefault();actions.hidden=false;save.focus();});
    }
    const box=this.root.querySelector('.history');box.append(el);box.scrollTop=box.scrollHeight;
  }
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


