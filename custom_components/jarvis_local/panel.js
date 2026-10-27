class JarvisLocalPanel extends HTMLElement {
  connectedCallback() { if (!this.root) this.setConfig({}); }
  set panel(panel) { this.setConfig(panel.config || {}); }
  setConfig(config) { this.config = config; if (!this.root) this.build(); this.loadInfo(); }
  set hass(hass) {
    this._hass = hass;
    if (!this.infoLoaded && !this.loadingInfo && this.root) this.loadInfo();
    if (this.root) {
      const id=this.config.agent_id || 'conversation.jarvis_local_test';
      const state=hass.states[id];
      this.root.querySelector('.connection').textContent='Agent: '+id+' | '+(state && state.state!=='unavailable' ? 'Available' : 'Not available')+' | v0.15.0';
    }
  }
  getCardSize() { return 7; }
  build() {
    this.root = this.attachShadow({mode:'open'});
    this.root.innerHTML = `<style>:host{display:block}ha-card[hidden]{display:none}ha-card{display:block;padding:24px;max-width:1000px;margin:20px auto;background:var(--card-background-color);border-radius:16px} :host{overflow:auto;height:100%;background:var(--primary-background-color);color:var(--primary-text-color)} .toolbar{display:flex;align-items:center;gap:14px;padding:12px 16px;background:var(--app-header-background-color,var(--card-background-color));color:var(--app-header-text-color,var(--primary-text-color));position:sticky;top:0;z-index:2}.menu{min-width:48px;min-height:48px;font-size:24px;border:0;background:transparent;color:inherit;cursor:pointer}.toolbar-title{font-size:20px;font-weight:500}.fallback{margin-left:auto;color:inherit;padding:12px} .tools{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}h2{margin-top:0}.history{min-height:180px;max-height:430px;overflow:auto;white-space:pre-wrap}.line{padding:10px;margin:6px 0;background:var(--secondary-background-color);border-radius:8px}form{display:flex;flex-wrap:wrap;gap:8px;margin-top:15px}form input{min-width:150px;flex:1 1 100%}input{flex:1;min-width:0;padding:12px}button{padding:12px 16px;min-height:48px;font-size:1rem;touch-action:manipulation} .quick-commands button{margin:4px;max-width:100%;overflow-wrap:anywhere} .quick-commands h3{margin:12px 0 4px}small{display:block;margin:10px 0;color:var(--secondary-text-color)}</style><header class="toolbar"><button type="button" class="menu" aria-label="Open Home Assistant menu" title="Open Home Assistant menu">☰</button><img src="/jarvis_local/logo.png" alt="" width="36" height="36" style="border-radius:9px"><span class="toolbar-title">Jarvis Local</span><button type="button" class="fallback open-settings">Jarvis settings</button><a href="/config" style="color:inherit">HA settings</a></header><ha-card class="settings-card" hidden><h2>Jarvis settings</h2><small>Choose your household entities. Lights and areas are discovered automatically. Leave a field blank to disable it or use automatic discovery where available.</small><div class="settings-fields"></div><h3>Switches used as lights</h3><small>Give each switch the name you use when speaking to Jarvis. The switch must be exposed to Assist.</small><div class="switch-fields"></div><div class="tools"><button type="button" class="add-switch">Add switch</button><button type="button" class="save-settings">Save settings</button><button type="button" class="close-settings">Back to chat</button></div><small class="settings-message" role="status"></small></ha-card><ha-card class="chat-card"><h2>Jarvis Local Chat</h2><small>Local commands, lighting and household status. Commands operate real devices. Preview a command first to inspect its targets.</small><small class="connection">Connecting to Home Assistant…</small><div class="tools"><button type="button" data-command="help">Help</button><button type="button" data-command="discover lights">Discover lights</button><button type="button" data-command="list zones">Zones</button><button type="button" data-command="which lights are on">Light status</button><button type="button" class="test-suite">Preview checks</button></div><section class="quick-commands" aria-label="Saved and frequently used commands"><h3>Favourites</h3><div class="favourites"></div><h3>Frequently used</h3><div class="frequent"></div><small>Tap a command to put it in the message box. Commands are stored on this device.</small><button type="button" class="favourite-current">Save typed command as favourite</button><button type="button" class="clear-frequent">Clear frequent commands</button><small class="quick-status" role="status"></small></section><label>Chat room <select class="room" aria-label="Chat room"><option value="">No room selected</option></select></label><details><summary>Diagnostics: recent voice and chat requests</summary><button type="button" class="refresh">Refresh diagnostics</button><button type="button" class="copy-diag">Copy diagnostics</button><span class="copy-status" role="status"></span><button type="button" class="clear-diag">Clear diagnostics</button><pre class="diagnostics" style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto"></pre></details><div class="history" role="log" aria-live="polite"></div><form><input aria-label="Message to Jarvis" placeholder="Type a command" required><button class="send">Send</button><button class="preview" type="button">Preview</button></form><button type="button" class="clear">Clear chat</button></ha-card>`;
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
    for (const button of this.root.querySelectorAll('[data-command]')) button.onclick = () => {this.root.querySelector('form input').value=button.dataset.command;this.send();};
    this.root.querySelector('.clear').onclick = () => {this.root.querySelector('.history').replaceChildren();this.conversationId=undefined;};
  }
  readQuick() {
    this.favourites=[];this.commandHistory=[];
    try {
      const value=JSON.parse(localStorage.getItem('jarvis_local_quick_commands_v1') || '{}');
      if(Array.isArray(value.favourites))this.favourites=value.favourites.filter(v=>typeof v==='string' && v.length<=150).slice(0,20);
      if(Array.isArray(value.history))this.commandHistory=value.history.filter(v=>v && typeof v.text==='string' && v.text.length<=150 && Number.isFinite(v.count) && v.count>0).slice(0,50);
    } catch(e) {this.quickStorageUnavailable=true;}
  }
  saveQuick() {
    try {localStorage.setItem('jarvis_local_quick_commands_v1',JSON.stringify({favourites:this.favourites,history:this.commandHistory}));this.quickStorageUnavailable=false;}
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
      button.onclick=()=>{const input=this.root.querySelector('form input');input.value=text;input.focus();};wrapper.append(button);
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
      this.settings=data.settings || {};
      this.infoLoaded=true;
    } catch(e) {this.root.querySelector('.diagnostics').textContent=e.message || String(e);}
    finally {this.loadingInfo=false;}
  }
  line(who, text) {const el=document.createElement('div');el.className='line';el.textContent=who+': '+text;const box=this.root.querySelector('.history');box.append(el);box.scrollTop=box.scrollHeight;}
  async send(preview=false) {
    if(this.busy)return;
    const input=this.root.querySelector('form input');const original=input.value.trim();if(!original)return;const text=(preview ? 'preview ' : '')+original;
    const agent=this.config.agent_id || 'conversation.jarvis_local_test';
    if(!this._hass?.states[agent] || this._hass.states[agent].state==='unavailable'){this.line('Status','Jarvis Local is not loaded. Check the integration startup logs. No command was sent.');return;}
    this.busy=true;this.root.querySelector('.send').disabled=true;input.value='';this.line('You',text);
    const start=performance.now();
    try {const request={type:'jarvis_local/process',text};const room=this.root.querySelector('.room').value;if(room)request.area_id=room;if(this.conversationId)request.conversation_id=this.conversationId;const reply=await this._hass.callWS(request);if(!preview)this.trackCommand(original);this.conversationId=reply.conversation_id;this.line('Jarvis',reply.response?.speech?.plain?.speech || '(No text reply. The routine may announce through the Bedroom Muse.)');this.line('Timing',Math.round(performance.now()-start)+' ms, including routine execution');}
    catch(e){this.line('Error',e.message || String(e));}
    finally{this.loadInfo();this.busy=false;this.root.querySelector('.send').disabled=false;input.focus();}
  }
}
if (!customElements.get('jarvis-local-panel')) customElements.define('jarvis-local-panel',JarvisLocalPanel);
