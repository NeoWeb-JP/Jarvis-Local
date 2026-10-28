const assert=require('assert'),fs=require('fs'),vm=require('vm');let Panel;
class Element{constructor(){this.children=[];this.listeners={};this.value='';this.textContent='';}append(...x){this.children.push(...x)}replaceChildren(){this.children=[];this.textContent=''}setAttribute(){}addEventListener(k,f){this.listeners[k]=f}focus(){}}
let allow=false,confirmed=0;const storage={};
const context={HTMLElement:class{},customElements:{get:()=>false,define:(_,v)=>Panel=v},document:{createElement:()=>new Element()},window:{confirm:()=>{confirmed++;return allow}},localStorage:{setItem:(k,v)=>storage[k]=v},console};
vm.runInNewContext(fs.readFileSync('custom_components/jarvis_local/panel.js','utf8'),context);
const p=new Panel();const els={'.favourites':new Element(),'.frequent':new Element(),'.quick-status':new Element(),'form input':new Element(),'.history':new Element(),'.quick-section':new Element()};p.root={querySelector:k=>els[k]};p.favourites=[];p.commandHistory=[];p.addFavourite('good morning');assert.equal(p.favourites[0],'good morning');
const remove=els['.favourites'].children[0].children[1];remove.onclick();assert.equal(confirmed,1);assert.equal(p.favourites.length,1);allow=true;remove.onclick();assert.equal(p.favourites.length,0);
p.line('You','office light on');let bubble=els['.history'].children[0],actions=bubble.children[1],btn=actions.children[0];bubble.listeners.contextmenu({preventDefault(){}});btn.onclick();assert.equal(p.favourites[0],'office light on');assert.equal(els['.quick-section'].open,true);
console.log('Favourites interactions passed.');
