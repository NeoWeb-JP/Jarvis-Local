const assert=require('assert'),fs=require('fs'),vm=require('vm');let Panel;
class Element{
  constructor(){this.children=[];this.textContent='';}
  append(...items){this.children.push(...items);}
  replaceChildren(){this.children=[];this.textContent='';}
}
const context={HTMLElement:class{},customElements:{get:()=>false,define:(_,cls)=>Panel=cls},document:{createElement:()=>new Element()},console};
vm.runInNewContext(fs.readFileSync('custom_components/jarvis_local/panel.js','utf8'),context);
const panel=new Panel(),container=new Element();
panel.root={querySelector:selector=>{assert.equal(selector,'.diagnostic-cards');return container;}};
const base={time:'2026-10-31T12:00:00Z',received_text:'Stop',resolved_text:'Stop',satellite_id:'assist_satellite.bedroom',response:'',steps:[],outcome:'completed'};
const reasons={
 missing_satellite:'No Assist satellite was supplied.',
 unmapped_satellite:'No media player is mapped to this satellite.',
 invalid_mapping:'The saved media player mapping is invalid.',
 service_error:'Media stop request failed. Check the Home Assistant log.',
 service_timeout:'Media stop request timed out. Playback is not verified.',
 request_sent:'Stop request sent. Playback and hardware interruption are not verified.',
};
for(const [reason,message] of Object.entries(reasons)){
 const called=['service_error','service_timeout','request_sent'].includes(reason);
 const record={...base,satellite_id:reason==='missing_satellite'?null:base.satellite_id,
 stop:{reason,service_called:called,media_player_id:called?'media_player.bedroom':null}};
 panel.renderDiagnostics([record]);
 const lines=container.children[0].children.map(child=>child.textContent);
 assert(lines.includes('Stop result: '+message));
 assert(lines.includes('Reply: Silent'));
 assert(lines.includes('Assist satellite: '+(record.satellite_id||'Not supplied')));
 assert(lines.includes('Stop player: '+(called?'media_player.bedroom':'None selected')));
 assert(lines.includes('Stop request: '+(called?'Attempted':'No service call')));
}
panel.renderDiagnostics([{...base,stop:{reason:'future_reason'}}]);
assert(container.children[0].children.some(child=>child.textContent==='Stop result: Unknown stop result.'));
panel.renderDiagnostics([base]);
assert.equal(container.children[0].children.length,7);
assert(!container.children[0].children.some(child=>child.textContent.startsWith('Stop result:')));
panel.renderDiagnostics([]);
assert.equal(container.children.length,0);
assert.match(container.textContent,/No Declan requests/);
const injected='<img src=x onerror=alert(1)>';
panel.renderDiagnostics([{...base,satellite_id:injected,stop:{reason:'unmapped_satellite'}}]);
assert(container.children[0].children.some(child=>child.textContent==='Assist satellite: '+injected));
console.log('Stop diagnostic cards passed.');
