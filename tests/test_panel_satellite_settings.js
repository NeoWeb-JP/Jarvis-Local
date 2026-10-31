const assert=require('assert'),fs=require('fs'),vm=require('vm');
let Panel;
class Element {
  constructor(tag='div'){this.style={};this.tag=tag;this.children=[];this.value='';this.textContent='';this.dataset={};this.disabled=false;this.hidden=false;}
  append(...items){for(const item of items){item.parent=this;this.children.push(item);}}
  add(option){this.append(option);}
  replaceChildren(){this.children=[];}
  remove(){this.parent.children=this.parent.children.filter(item=>item!==this);}
  setAttribute(){}
  focus(){this.focused=true;}
  querySelectorAll(selector){const out=[];const walk=e=>{for(const child of e.children){if(selector.startsWith('.')?(child.className||'').split(' ').includes(selector.slice(1)):child.tag===selector)out.push(child);walk(child);}};walk(this);return out;}
  querySelector(selector){return this.querySelectorAll(selector)[0];}
}
const context={HTMLElement:class{},customElements:{get:()=>false,define:(_,cls)=>Panel=cls},
 document:{createElement:tag=>new Element(tag),createTextNode:text=>Object.assign(new Element('text'),{textContent:text})},
 Option:class extends Element{constructor(text,value){super('option');this.textContent=text;this.value=value;}},console};
vm.runInNewContext(fs.readFileSync('custom_components/jarvis_local/panel.js','utf8'),context);
const bedroom='assist_satellite.bedroom',kitchen='assist_satellite.kitchen';
function fixture(){
 const panel=new Panel(),els={};
 for(const name of ['satellite-fields','satellite-empty','add-satellite','settings-message','settings-fields','switch-fields','profile-fields','profile-message','save-settings','check-satellite-mappings','satellite-check-message','satellite-check-results'])els['.'+name]=new Element();
 const controls=()=>[...els['.satellite-fields'].querySelectorAll('select'),...els['.satellite-fields'].querySelectorAll('button'),els['.add-satellite'],els['.save-settings'],els['.check-satellite-mappings']];
 panel.root={querySelector:s=>els[s],querySelectorAll:s=>{
   if(s==='.satellite-row')return els['.satellite-fields'].children;
   if(s==='.settings-fields select')return els['.settings-fields'].querySelectorAll('select');
   if(s==='.switch-fields > div')return [];
   if(s.startsWith('.settings-card'))return controls();
   throw Error('Unexpected selector '+s);
 }};
 const calls=[];
 panel._hass={states:Object.fromEntries([bedroom,kitchen,'media_player.bedroom','media_player.kitchen','weather.home'].map(id=>[id,{entity_id:id,attributes:{friendly_name:'Name <safe>'}}])),
 callWS:async request=>{calls.push(request);}};
 panel.loadInfo=async()=>{};
 panel.showSettings=open=>{panel.open=open;};
 return {panel,els,calls,controls};
}
(async()=>{
 const {panel,els,calls,controls}=fixture();
 panel.settings={weather:'weather.home',satellite_media_players:{[bedroom]:'media_player.bedroom'}};
 await panel.openSettings();
 assert.equal(panel.open,true);
 assert.equal(els['.satellite-fields'].children.length,1);
 let row=els['.satellite-fields'].children[0];
 assert.equal(row.querySelector('.satellite-source').value,bedroom);
 assert.equal(row.querySelector('.satellite-player').value,'media_player.bedroom');
 // Add never guesses a player, even with a matching room name.
 panel.addSatelliteRow();
 row=els['.satellite-fields'].children[1];
 assert.equal(row.querySelector('.satellite-source').value,'');
 assert.equal(row.querySelector('.satellite-player').value,'');
 await panel.saveSettings();assert.equal(calls.length,0);
 assert.match(els['.settings-message'].textContent,/unique Assist satellite/);
 row.querySelector('.satellite-source').value=bedroom;
 row.querySelector('.satellite-player').value='media_player.kitchen';
 await panel.saveSettings();assert.equal(calls.length,0);
 row.querySelector('.satellite-source').value=kitchen;
 await panel.saveSettings();
 assert.equal(calls.length,1);
 assert.deepEqual(JSON.parse(JSON.stringify(calls[0].settings.satellite_media_players)),{[bedroom]:'media_player.bedroom',[kitchen]:'media_player.kitchen'});
 assert.equal(calls[0].settings.weather,'weather.home');
 assert.match(els['.settings-message'].textContent,/active now/);
 // Settings save calls only the settings endpoint, with no playback/service calls.
 assert.equal(calls[0].type,'jarvis_local/save_settings');
 await panel.openSettings();
 assert.equal(els['.satellite-fields'].children.length,2);
 // Removing all rows sends an explicit empty dictionary.
 for(const item of [...els['.satellite-fields'].children])item.children.at(-1).onclick();
 assert.equal(els['.satellite-empty'].hidden,false);
 await panel.saveSettings();
 assert.deepEqual(JSON.parse(JSON.stringify(calls.at(-1).settings.satellite_media_players)),{});
 // Missing saved entities remain visible with their exact values.
 panel.settings={satellite_media_players:{'assist_satellite.missing':'media_player.missing'}};
 await panel.openSettings();
 row=els['.satellite-fields'].children[0];
 assert.equal(row.querySelector('.satellite-source').children.at(-1).textContent,'Missing: assist_satellite.missing');
 assert.equal(row.querySelector('.satellite-player').value,'media_player.missing');
 await panel.saveSettings();assert.equal(calls.at(-1).settings.satellite_media_players['assist_satellite.missing'],'media_player.missing');
 // A failed save retains selections and re-enables controls.
 const before=panel.settings;
 panel._hass.callWS=async()=>{throw Error('Connection lost');};
 await panel.saveSettings();
 assert.equal(panel.settings,before);
 assert.equal(row.querySelector('.satellite-player').value,'media_player.missing');
 assert.match(els['.settings-message'].textContent,/Connection lost/);
 assert(controls().every(control=>!control.disabled));
 // Pending saves lock the editor, preventing edits from being silently discarded.
 let finish;
 panel._hass.callWS=()=>new Promise(resolve=>{finish=resolve;});
 const saving=panel.saveSettings();
 assert(controls().every(control=>control.disabled));
 finish({});await saving;
 assert(controls().every(control=>!control.disabled));
 // Respect the server's mapping limit and restore Add after removing a row.
 els['.satellite-fields'].replaceChildren();
 for(let i=0;i<51;i++)panel.addSatelliteRow('assist_satellite.room_'+i,'media_player.room_'+i);
 assert.equal(els['.satellite-fields'].children.length,50);
 assert.equal(els['.add-satellite'].disabled,true);
 els['.satellite-fields'].children[0].children.at(-1).onclick();
 assert.equal(els['.add-satellite'].disabled,false);

 // Saved mapping checks use a read-only endpoint and leave unsaved selections intact.
 const health=fixture(),hp=health.panel,he=health.els;
 hp.addSatelliteRow(bedroom,'media_player.kitchen');
 const pendingRow=he['.satellite-fields'].children[0];
 const result={mappings:[{satellite_id:bedroom,media_player_id:'media_player.bedroom',
   satellite_status:'available',player_status:'available',entities_available:true,shared_player:true}],error:null};
 hp._hass.callWS=async request=>{health.calls.push(request);return result;};
 await hp.checkSatelliteMappings();
 assert.deepEqual(JSON.parse(JSON.stringify(health.calls)),[{type:'jarvis_local/check_satellite_mappings'}]);
 assert.equal(pendingRow.querySelector('.satellite-player').value,'media_player.kitchen');
 assert.match(he['.satellite-check-message'].textContent,/Unsaved edits are not included/);
 const text=he['.satellite-check-results'].children[0].children.map(e=>e.textContent).join('\n');
 assert.match(text,/Both entities are available/);
 assert.match(text,/Confirm this is intentional/);
 assert.match(text,/remain unverified/);
 // Missing and unavailable states are described without implying that playback was tested.
 result.mappings[0].satellite_status='missing';result.mappings[0].player_status='unavailable';
 result.mappings[0].entities_available=false;result.mappings[0].shared_player=false;
 await hp.checkSatelliteMappings();
 const problem=he['.satellite-check-results'].children[0].children.map(e=>e.textContent).join('\n');
 assert.match(problem,/Entity missing/);assert.match(problem,/Unavailable/);assert.match(problem,/Review this mapping/);
 assert(!problem.includes('Shared player'));
 // Empty results, server validation errors and connection failures cannot leave old cards visible.
 hp._hass.callWS=async()=>({mappings:[],error:null});
 await hp.checkSatelliteMappings();
 assert.equal(he['.satellite-check-results'].children.length,0);
 assert.match(he['.satellite-check-message'].textContent,/No saved mappings/);
 hp._hass.callWS=async()=>({mappings:[],error:'Saved mappings are invalid'});
 await hp.checkSatelliteMappings();
 assert.match(he['.satellite-check-message'].textContent,/invalid/);
 hp._hass.callWS=async()=>{throw Error('offline');};
 await hp.checkSatelliteMappings();
 assert.match(he['.satellite-check-message'].textContent,/offline/);
 assert.equal(he['.check-satellite-mappings'].disabled,false);
 // A response for an earlier settings view is discarded.
 let resolveCheck;
 hp._hass.callWS=()=>new Promise(resolve=>{resolveCheck=resolve;});
 const late=hp.checkSatelliteMappings();
 hp.clearSatelliteCheck();
 resolveCheck(result);await late;
 assert.equal(he['.satellite-check-results'].children.length,0);
 assert.equal(he['.satellite-check-message'].textContent,'');
 // Overlapping check and save completions must not leave either button stuck.
 let resolveSave;
 hp._hass.callWS=request=>new Promise(resolve=>{
   if(request.type==='jarvis_local/save_settings')resolveSave=resolve;else resolveCheck=resolve;
 });
 const checkThenSave=hp.checkSatelliteMappings();
 const concurrentSave=hp.saveSettings();
 resolveCheck(result);await checkThenSave;
 assert.equal(he['.check-satellite-mappings'].disabled,true);
 resolveSave({});await concurrentSave;
 assert.equal(he['.check-satellite-mappings'].disabled,false);
 assert.equal(he['.satellite-check-results'].children.length,0);
 const checkLast=hp.checkSatelliteMappings();
 const saveFirst=hp.saveSettings();
 resolveSave({});await saveFirst;
 assert.equal(he['.check-satellite-mappings'].disabled,true);
 resolveCheck(result);await checkLast;
 assert.equal(he['.check-satellite-mappings'].disabled,false);
 assert.equal(he['.satellite-check-results'].children.length,0);

 console.log('Satellite mapping editor and saved health checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
