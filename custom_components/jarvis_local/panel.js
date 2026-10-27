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
      this.root.querySelector('.connection').textContent='Agent: '+id+' | '+(state && state.state!=='unavailable' ? 'Available' : 'Not available')+' | v0.9.1';
    }
  }
  getCardSize() { return 7; }
  build() {
    this.root = this.attachShadow({mode:'open'});
    this.root.innerHTML = `<style>:host{display:block}ha-card{display:block;padding:24px;max-width:1000px;margin:20px auto;background:var(--card-background-color);border-radius:16px} :host{overflow:auto;height:100%;background:var(--primary-background-color);color:var(--primary-text-color)} .toolbar{display:flex;align-items:center;gap:14px;padding:12px 16px;background:var(--app-header-background-color,var(--card-background-color));color:var(--app-header-text-color,var(--primary-text-color));position:sticky;top:0;z-index:2}.menu{min-width:48px;min-height:48px;font-size:24px;border:0;background:transparent;color:inherit;cursor:pointer}.toolbar-title{font-size:20px;font-weight:500}.fallback{margin-left:auto;color:inherit;padding:12px} .tools{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}h2{margin-top:0}.history{min-height:180px;max-height:430px;overflow:auto;white-space:pre-wrap}.line{padding:10px;margin:6px 0;background:var(--secondary-background-color);border-radius:8px}form{display:flex;flex-wrap:wrap;gap:8px;margin-top:15px}form input{min-width:150px;flex:1 1 100%}input{flex:1;min-width:0;padding:12px}button{padding:10px}small{display:block;margin:10px 0;color:var(--secondary-text-color)}</style><header class="toolbar"><button type="button" class="menu" aria-label="Open Home Assistant menu" title="Open Home Assistant menu">☰</button><span class="toolbar-title">Jarvis Local</span><a class="fallback" href="/config">Settings</a></header><ha-card><h2>Jarvis Local Chat</h2><small>Local commands, lighting and household status. Commands operate real devices. Preview a command first to inspect its targets.</small><small class="connection">Connecting to Home Assistant…</small><div class="tools"><button type="button" data-command="help">Help</button><button type="button" data-command="discover lights">Discover lights</button><button type="button" data-command="list zones">Zones</button><button type="button" data-command="which lights are on">Light status</button><button type="button" class="test-suite">Preview checks</button></div><label>Chat room <select class="room" aria-label="Chat room"><option value="">No room selected</option></select></label><details><summary>Diagnostics: recent voice and chat requests</summary><button type="button" class="refresh">Refresh diagnostics</button><button type="button" class="clear-diag">Clear diagnostics</button><pre class="diagnostics" style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto"></pre></details><div class="history" role="log" aria-live="polite"></div><form><input aria-label="Message to Jarvis" placeholder="Type a command" required><button class="send">Send</button><button class="preview" type="button">Preview</button></form><button type="button" class="clear">Clear chat</button></ha-card>`;
    this.root.querySelector('.menu').onclick = () => this.dispatchEvent(new Event('hass-toggle-menu', {bubbles:true, composed:true}));
    this.root.querySelector('.test-suite').onclick=()=>this.previewChecks();
    this.root.querySelector('.refresh').onclick=()=>this.loadInfo();
    this.root.querySelector('.clear-diag').onclick=async()=>{await this._hass.callWS({type:'jarvis_local/clear_diagnostics'});this.loadInfo();};
    this.root.querySelector('form').onsubmit = e => { e.preventDefault(); this.send(); };
    this.root.querySelector('.preview').onclick = () => this.send(true);
    for (const button of this.root.querySelectorAll('[data-command]')) button.onclick = () => {this.root.querySelector('input').value=button.dataset.command;this.send();};
    this.root.querySelector('.clear').onclick = () => {this.root.querySelector('.history').replaceChildren();this.conversationId=undefined;};
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
      this.infoLoaded=true;
    } catch(e) {this.root.querySelector('.diagnostics').textContent=e.message || String(e);}
    finally {this.loadingInfo=false;}
  }
  line(who, text) {const el=document.createElement('div');el.className='line';el.textContent=who+': '+text;const box=this.root.querySelector('.history');box.append(el);box.scrollTop=box.scrollHeight;}
  async send(preview=false) {
    if(this.busy)return;
    const input=this.root.querySelector('input');const original=input.value.trim();if(!original)return;const text=(preview ? 'preview ' : '')+original;
    const agent=this.config.agent_id || 'conversation.jarvis_local_test';
    if(!this._hass?.states[agent] || this._hass.states[agent].state==='unavailable'){this.line('Status','Jarvis Local is not loaded. Check the integration startup logs. No command was sent.');return;}
    this.busy=true;this.root.querySelector('.send').disabled=true;input.value='';this.line('You',text);
    const start=performance.now();
    try {const request={type:'jarvis_local/process',text};const room=this.root.querySelector('.room').value;if(room)request.area_id=room;if(this.conversationId)request.conversation_id=this.conversationId;const reply=await this._hass.callWS(request);this.conversationId=reply.conversation_id;this.line('Jarvis',reply.response?.speech?.plain?.speech || '(No text reply. The routine may announce through the Bedroom Muse.)');this.line('Timing',Math.round(performance.now()-start)+' ms, including routine execution');}
    catch(e){this.line('Error',e.message || String(e));}
    finally{this.loadInfo();this.busy=false;this.root.querySelector('.send').disabled=false;input.focus();}
  }
}
if (!customElements.get('jarvis-local-panel')) customElements.define('jarvis-local-panel',JarvisLocalPanel);
