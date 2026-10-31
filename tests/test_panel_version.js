const assert=require('assert'),fs=require('fs'),vm=require('vm');let Panel;
const context={HTMLElement:class{},customElements:{get:()=>false,define:(_,cls)=>Panel=cls},
 Option:class{constructor(text,value){this.text=text;this.value=value;}},console};
vm.runInNewContext(fs.readFileSync('custom_components/jarvis_local/panel.js','utf8'),context);
(async()=>{
 const panel=new Panel();
 const els={'.connection':{},'.room':{value:'',replaceChildren(){},add(){}},
 '.debug-toggle':{},'.debug-content':{},'.diagnostics':{},'.overview-agent':{}};
 panel.root={querySelector:selector=>{assert(els[selector],'Unexpected selector '+selector);return els[selector];}};
 panel.config={};
 panel.renderDiagnostics=()=>{};
 panel.updateOverview=()=>{};
 panel.voicePipelines=[];
 let version='0.34.2';
 const hass={states:{},callWS:async request=>{
   assert.equal(request.type,'jarvis_local/info');
   return {version,areas:[],diagnostics:[],settings:{},voice_profiles:{},debug_enabled:false};
 }};
 panel._hass=hass;
 await panel.loadInfo();
 assert.equal(els['.connection'].textContent,'v0.34.2');
 // Normal state updates must not reset the version to a stale frontend literal.
 panel.hass=hass;
 assert.equal(els['.connection'].textContent,'v0.34.2');
 version='0.34.3';
 await panel.loadInfo();
 assert.equal(els['.connection'].textContent,'v0.34.3');
 panel.hass=hass;
 assert.equal(els['.connection'].textContent,'v0.34.3');
 for(const missing of [undefined,null,'',123]){
   version=missing;await panel.loadInfo();
   assert.equal(els['.connection'].textContent,'Installed version unavailable');
 }
 hass.callWS=async()=>{throw Error('offline');};
 await panel.loadInfo();
 assert.equal(els['.connection'].textContent,'Installed version unavailable');
 console.log('Installed version reporting passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
