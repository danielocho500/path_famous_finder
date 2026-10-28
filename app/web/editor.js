const base = location.pathname.replace(/\/editor\/?$/, '') + '/api/v1';
const $ = id => document.getElementById(id);
const fields = {
  people: [
    ['name','Nombre','text',true], ['aliases','Alias (separados por coma)','text'],
    ['description','Descripción','textarea'], ['country','País','text'],
    ['city_born','Ciudad de nacimiento','text'], ['image_url','URL de imagen','url'],
    ['wikidata_id','ID de Wikidata','text'], ['birth_year','Año de nacimiento (AEC negativo)','number'],
    ['death_year','Año de fallecimiento (AEC negativo)','number'],
  ],
  sources: [
    ['title','Título','text',true], ['url','URL','url'], ['citation','Cita bibliográfica o archivo','textarea'],
    ['author','Autor','text'], ['publisher','Editorial / institución','text'],
    ['accessed_at','Fecha de consulta','date'],
    ['loc_name','Lugar / Sede de archivo o publicación','text'],
    ['loc_city','Ciudad','text'],
    ['loc_country','País (ej. FR, IT)','text'],
    ['loc_lat','Latitud','number'],
    ['loc_lng','Longitud','number'],
  ],
  organizations: [
    ['name','Nombre','text',true], ['kind','Tipo','select',true,['team','government','institution','other']],
    ['description','Descripción','textarea'],
  ],
  works: [
    ['name','Título','text',true], ['kind','Tipo','select',true,['film','music','book','artwork','project','other']],
    ['start_year','Año inicial','number'], ['end_year','Año final','number'],
    ['description','Descripción','textarea'],
  ],
  events: [
    ['name','Título del evento','text',true], ['kind','Tipo','select',true,['sports.match','arts.performance','politics.treaty_signing','politics.meeting','personal.meeting','other']],
    ['start_year','Año inicial','number'], ['end_year','Año final','number'], ['place','Lugar (nombre)','text'],
    ['loc_city','Ciudad','text'],
    ['loc_country','País (ej. FR, IT)','text'],
    ['loc_lat','Latitud','number'],
    ['loc_lng','Longitud','number'],
    ['source_id','Fuente del evento','source',true], ['source_locator','Localizador de la fuente','text',true],
  ],
};
const titles = {people:'persona',sources:'fuente',organizations:'organización',works:'obra',events:'evento'};
let catalog = [], cache = {people:[],sources:[],organizations:[],works:[],events:[],facts:[]};
let entityCurrent = null, factCurrent = null, noticeTimer;

async function api(path, options = {}) {
  const response = await fetch(base + path, {headers:{'Content-Type':'application/json'}, ...options});
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body));
  }
  return response.json();
}
function notice(message, error=false) {
  const box = $('notice'); box.textContent=message; box.hidden=false; box.className=error?'error':'';
  clearTimeout(noticeTimer); noticeTimer=setTimeout(()=>box.hidden=true,7000);
}
function fail(error) { console.error(error); notice(error.message || String(error),true); }
function option(select, value, label) {
  const node=document.createElement('option'); node.value=value; node.textContent=label; select.append(node);
}
function setOptions(select, items, placeholder, selected='') {
  select.replaceChildren(); option(select,'',placeholder);
  for (const item of items) option(select,item.id,item.name||item.title||item.id);
  select.value=selected || '';
}
function yearDate(value) { return value === '' || value == null ? null : {year:Number(value),precision:'year'}; }
function keepDate(original,value) { return original && String(original.year)===String(value) ? original : yearDate(value); }
function yearValue(date) { return date?.year ?? ''; }
function str(value) { return value == null ? '' : String(value); }

async function loadCollection(name, q='') {
  const data=await api('/'+name+'?limit=200'+(q?'&q='+encodeURIComponent(q):''));
  if (name!=='facts') {
    const known=new Map((cache[name]||[]).map(item=>[item.id,item]));
    for(const item of data) known.set(item.id,item);
    cache[name]=[...known.values()];
  } else if(!q) cache[name]=data;
  return data;
}
function bindSelectSearch(inputId,selectId,collectionFor,filterFor=()=>true) {
  let timer;
  $(inputId).oninput=()=>{
    clearTimeout(timer);
    timer=setTimeout(async()=>{
      try {
        const select=$(selectId), old=select.selectedOptions[0];
        const oldValue=select.value, oldText=old?.textContent;
        const collection=collectionFor();
        const found=(await loadCollection(collection,$(inputId).value.trim())).filter(filterFor);
        setOptions(select,found,'Selecciona un registro',oldValue);
        if(oldValue && ![...select.options].some(x=>x.value===oldValue)) {
          option(select,oldValue,oldText||oldValue);select.value=oldValue;
        }
      } catch(error){fail(error);}
    },250);
  };
}
async function refreshChoices() {
  await Promise.all(['people','sources','organizations','works','events'].map(name=>loadCollection(name)));
  const {people,sources}=cache;
  setOptions($('subject-id'),people,'Selecciona una persona',$('subject-id').value);
  setOptions($('peer-id'),people,'Sin segunda persona',$('peer-id').value);
  setOptions($('review-person'),people,'Selecciona una persona',$('review-person').value);
  setOptions($('source-id'),sources,'Selecciona una fuente',$('source-id').value);
  setOptions($('peer-source-id'),sources,'Selecciona una fuente',$('peer-source-id').value);
  await updateObjectOptions();
  if ($('collection').value==='events') renderEntityFields();
}
function showView(name) {
  document.querySelectorAll('.view').forEach(el=>el.classList.toggle('active',el.id===name));
  document.querySelectorAll('[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===name));
  if (name==='review') refreshReview().catch(fail);
}
function renderEntityFields() {
  const collection=$('collection').value, container=$('entity-fields'); container.replaceChildren();
  for (const [key,label,type,required,values] of fields[collection]) {
    const wrap=document.createElement('label'); wrap.textContent=label;
    if (type==='textarea') wrap.classList.add('full');
    let input;
    if (type==='textarea') input=document.createElement('textarea');
    else if (type==='select' || type==='source') input=document.createElement('select');
    else {input=document.createElement('input');input.type=type;}
    input.id='entity-'+key; input.required=!!required;
    if (type==='select') for (const value of values) option(input,value,value);
    if (type==='source') setOptions(input,cache.sources,'Selecciona una fuente');
    wrap.append(input);container.append(wrap);
  }
  $('entity-title').textContent=entityCurrent ? 'Editar '+titles[collection] : 'Nueva '+titles[collection];
  $('entity-mode').textContent=entityCurrent?'EDICIÓN · REVISIÓN '+entityCurrent.revision:'NUEVO REGISTRO';
  if (entityCurrent) {
    for (const [key] of fields[collection]) {
      let value=entityCurrent[key];
      if (key==='aliases') value=(value||[]).join(', ');
      if (key==='birth_year') value=yearValue(entityCurrent.birth);
      if (key==='death_year') value=yearValue(entityCurrent.death);
      if (key==='start_year') value=yearValue(entityCurrent.period?.start);
      if (key==='end_year') value=yearValue(entityCurrent.period?.end);
      if (key==='loc_name') value=entityCurrent.location?.name;
      if (key==='loc_city') value=entityCurrent.location?.city;
      if (key==='loc_country') value=entityCurrent.location?.country;
      if (key==='loc_lat') value=entityCurrent.location?.lat;
      if (key==='loc_lng') value=entityCurrent.location?.lng;
      $('entity-'+key).value=str(value);
    }
  }
  renderEntityExtras().catch(fail);
}
async function renderEntityExtras() {
  const box=$('entity-extras'), selected=entityCurrent, collection=$('collection').value;
  box.replaceChildren();if(!selected)return;
  const requests=[api('/'+collection+'/'+selected.id+'/history')];
  if(collection==='sources') requests.push(api('/sources/'+selected.id+'/facts'));
  const [history,linked]=await Promise.all(requests);
  if(entityCurrent?.id!==selected.id || $('collection').value!==collection)return;
  const heading=document.createElement('h4');heading.textContent='Historial de cambios';box.append(heading);
  for(const entry of history.slice(0,8)){
    const row=document.createElement('p');row.className='audit-row';
    row.textContent='Revisión '+entry.revision+' · '+entry.action+' · '+entry.at;
    box.append(row);
  }
  if(collection==='sources'){
    const title=document.createElement('h4');title.textContent='Hechos que usan esta fuente';box.append(title);
    if(!linked.length){const p=document.createElement('p');p.className='empty';p.textContent='Ningún hecho usa esta fuente todavía.';box.append(p);}
    for(const item of linked){const button=document.createElement('button');button.type='button';button.className='record';
      button.textContent=(catalog.find(x=>x.id===item.type_id)?.label||item.type_id)+' · '+item.status;
      button.onclick=()=>editFact(item);box.append(button);}
  }
}
function readEntity() {
  const collection=$('collection').value, data={};
  for (const [key] of fields[collection]) data[key]=$('entity-'+key).value.trim();
  if (collection==='people') {
    data.aliases=data.aliases?data.aliases.split(',').map(x=>x.trim()).filter(Boolean):[];
    data.birth=keepDate(entityCurrent?.birth,data.birth_year);
    data.death=keepDate(entityCurrent?.death,data.death_year);
    delete data.birth_year;delete data.death_year;
  }
  if (collection==='works'||collection==='events') {
    data.period={start:keepDate(entityCurrent?.period?.start,data.start_year),
                 end:keepDate(entityCurrent?.period?.end,data.end_year)};
    delete data.start_year;delete data.end_year;
  }
  if (['sources','events'].includes(collection)) {
    const locName = data.loc_name || data.place;
    const locCity = data.loc_city;
    const locCountry = data.loc_country;
    const locLat = data.loc_lat;
    const locLng = data.loc_lng;
    if (locName || locCity || locCountry || locLat || locLng) {
      data.location = {
        name: locName || locCity || 'Ubicación',
        city: locCity || null,
        country: locCountry || null,
        lat: locLat !== '' && locLat != null ? Number(locLat) : null,
        lng: locLng !== '' && locLng != null ? Number(locLng) : null,
      };
    } else {
      data.location = null;
    }
    delete data.loc_name; delete data.loc_city; delete data.loc_country;
    delete data.loc_lat; delete data.loc_lng;
  }
  for (const key of Object.keys(data)) if (data[key]==='' && !['name','title','source_locator'].includes(key)) data[key]=null;
  return data;
}
async function renderEntityList(q='') {
  const collection=$('collection').value, items=await loadCollection(collection,q);
  const list=$('entity-list');list.replaceChildren();
  if (!items.length){const p=document.createElement('p');p.className='empty';p.textContent='No hay registros todavía.';list.append(p);return;}
  for (const item of items){
    const button=document.createElement('button');button.type='button';button.className='record';
    const title=document.createElement('strong');title.textContent=item.name||item.title;
    const detail=document.createElement('span');detail.textContent=(item.kind||item.citation||item.country||'')+' · revisión '+item.revision;
    button.append(title,detail);button.onclick=()=>{entityCurrent=item;renderEntityFields();};list.append(button);
  }
}
async function saveEntity(event) {
  event.preventDefault(); const collection=$('collection').value, data=readEntity();
  try {
    const wasEdit=!!entityCurrent;
    const saved=entityCurrent
      ? await api('/'+collection+'/'+entityCurrent.id,{method:'PATCH',body:JSON.stringify({revision:entityCurrent.revision,changes:data})})
      : await api('/'+collection,{method:'POST',body:JSON.stringify(data)});
    entityCurrent=saved;renderEntityFields();await refreshChoices();await renderEntityList($('search').value);
    notice(wasEdit && ['sources','organizations','works','events'].includes(collection)
      ? 'Registro guardado. Los hechos verificados dependientes vuelven a borrador para revisión.'
      : 'Registro guardado. Revisión '+saved.revision+'.');
  } catch(error){fail(error);}
}
function populateTypes() {
  const supertypes=[...new Set(catalog.map(item=>item.supertype))];
  const selected=$('supertype').value;
  $('supertype').replaceChildren();for(const name of supertypes)option($('supertype'),name,name);
  $('supertype').value=selected||supertypes[0];updateTypes();
}
function updateTypes() {
  const selected=$('type-id').value;
  $('type-id').replaceChildren();
  for (const item of catalog.filter(x=>x.supertype===$('supertype').value)) option($('type-id'),item.id,item.label);
  if ([...$('type-id').options].some(x=>x.value===selected))$('type-id').value=selected;
  updateObjectOptions().catch(fail);
}
function selectedType(){return catalog.find(item=>item.id===$('type-id').value);}
async function updateObjectOptions() {
  const type=selectedType();if(!type)return;
  const collection={person:'people',organization:'organizations',work:'works',event:'events'}[type.context_kind];
  const previous=$('object-id').value;
  let options=cache[collection]||[];
  if (type.context_type)options=options.filter(item=>item.kind===type.context_type);
  setOptions($('object-id'),options,'Selecciona '+({people:'una persona',organizations:'una organización',works:'una obra',events:'un evento'}[collection]),previous);
  $('object-label').firstChild.textContent=type.shape==='direct'?'Segunda persona':'Contexto compartido';
  $('peer-fields').hidden=type.shape==='direct'||!!factCurrent;
  if(type.shape==='direct')$('peer-id').value='';
  $('role').required=!!type.roles;
  $('side').required=!!type.pair_rule;
  updatePeerRequirements();
  $('preview-title').textContent=type.label;
  const requirements=[];
  if(type.context_type)requirements.push('Contexto: '+type.context_type);
  if(type.roles)requirements.push('Roles: '+type.roles.join(', '));
  if(type.pair_rule)requirements.push(type.pair_rule==='opposite_side'?'Las personas deben estar en bandos distintos.':'Las personas deben estar en el mismo bando.');
  if(type.requires_period)requirements.push('Cada membresía necesita fechas que se solapen.');
  $('preview-text').textContent=requirements.join(' ')||'Este hecho conecta directamente a dos personas.';
}
function updatePeerRequirements(){
  const active=!!$('peer-id').value && selectedType()?.shape!=='direct' && !factCurrent;
  $('peer-source-id').required=active;
  $('peer-source-locator').required=active;
  $('peer-role').required=active && !!selectedType()?.roles;
  $('peer-side').required=active && !!selectedType()?.pair_rule;
}
function resetFact() {
  factCurrent=null;$('fact-form').reset();$('fact-mode').textContent='NUEVA CONEXIÓN';
  $('fact-verify').hidden=true;$('fact-archive').hidden=true;
  $('fact-loc-name').value='';$('fact-loc-city').value='';$('fact-loc-country').value='';
  $('fact-loc-lat').value='';$('fact-loc-lng').value='';
  updateObjectOptions().catch(fail);
}
function readFact(peer=false) {
  const value=id=>$(id).value.trim();
  const subject=peer?value('peer-id'):value('subject-id');
  const locName=value('fact-loc-name'), locCity=value('fact-loc-city'), locCountry=value('fact-loc-country');
  const locLat=value('fact-loc-lat'), locLng=value('fact-loc-lng');
  const location = (!peer && (locName || locCity || locCountry || locLat || locLng)) ? {
    name: locName || locCity || 'Ubicación',
    city: locCity || null,
    country: locCountry || null,
    lat: locLat !== '' ? Number(locLat) : null,
    lng: locLng !== '' ? Number(locLng) : null,
  } : null;
  return {type_id:value('type-id'),subject_id:subject,object_id:value('object-id'),
    source_id:peer?value('peer-source-id'):value('source-id'),
    source_locator:peer?value('peer-source-locator'):value('source-locator'),
    role:(peer?value('peer-role'):value('role'))||null,
    side:(peer?value('peer-side'):value('side'))||null,
    period:{start:keepDate(!peer?factCurrent?.period?.start:null,value('fact-start')),
            end:keepDate(!peer?factCurrent?.period?.end:null,value('fact-end'))},status:'draft',
    note:peer?null:value('fact-note')||null,
    location:peer?null:location};
}
async function saveFact(event) {
  event.preventDefault();
  try {
    const first=readFact();let saved;
    if(factCurrent) {
      const {status,...changes}=first;
      saved=await api('/facts/'+factCurrent.id,{method:'PATCH',body:JSON.stringify({revision:factCurrent.revision,changes})});
      factCurrent=saved;
    } else {
      const facts=[first];
      if ($('peer-id').value && selectedType()?.shape!=='direct') {
        if ($('peer-id').value===$('subject-id').value) throw Error('Elige dos personas distintas.');
        facts.push(readFact(true));
      }
      saved=await api('/facts/batch',{method:'POST',body:JSON.stringify({facts})});
      resetFact();
    }
    notice('Hecho guardado como borrador. Revisa la evidencia y verifica cada participación.');
    await refreshReview();
  } catch(error){fail(error);}
}
function editFact(item) {
  showView('connections');factCurrent=item;
  const spec=catalog.find(x=>x.id===item.type_id);
  $('supertype').value=spec.supertype;updateTypes();$('type-id').value=item.type_id;
  updateObjectOptions().then(()=>{
    $('subject-id').value=item.subject_id;$('object-id').value=item.object_id;
    $('source-id').value=item.source_id;$('source-locator').value=item.source_locator;
    $('role').value=item.role||'';$('side').value=item.side||'';
    $('fact-start').value=yearValue(item.period?.start);$('fact-end').value=yearValue(item.period?.end);
    $('fact-note').value=item.note||'';
    $('fact-loc-name').value=item.location?.name||'';
    $('fact-loc-city').value=item.location?.city||'';
    $('fact-loc-country').value=item.location?.country||'';
    $('fact-loc-lat').value=item.location?.lat ?? '';
    $('fact-loc-lng').value=item.location?.lng ?? '';
    $('fact-mode').textContent='EDITAR HECHO · REVISIÓN '+item.revision;
    $('fact-verify').hidden=item.status!=='draft';$('fact-archive').hidden=item.status==='archived';
  }).catch(fail);
}
async function factAction(action) {
  if(!factCurrent)return;
  try {
    const item=await api('/facts/'+factCurrent.id+'/'+action,{method:'POST',body:JSON.stringify({revision:factCurrent.revision,changes:{}})});
    factCurrent=item;editFact(item);notice(action==='verify'?'Hecho verificado.':'Hecho archivado.');await refreshReview();
  } catch(error){fail(error);}
}
function nameFor(collection,id){return cache[collection]?.find(x=>x.id===id)?.name||id;}
async function refreshReview() {
  const items=await loadCollection('facts');const list=$('fact-list');list.replaceChildren();
  if(!items.length){const p=document.createElement('p');p.className='empty';p.textContent='Todavía no hay hechos.';list.append(p);}
  for(const item of items){
    const spec=catalog.find(x=>x.id===item.type_id), button=document.createElement('button');
    button.type='button';button.className='record';
    const title=document.createElement('strong');title.textContent=spec?.label||item.type_id;
    const detail=document.createElement('span');detail.textContent=nameFor('people',item.subject_id)+' → '+nameFor(item.object_collection,item.object_id);
    const status=document.createElement('small');status.className='badge '+item.status;status.textContent=item.status+' · revisión '+item.revision;
    button.append(title,detail,status);button.onclick=()=>editFact(item);list.append(button);
  }
  await renderConnections();
}
async function renderConnections() {
  const person=$('review-person').value,list=$('connection-list');list.replaceChildren();
  if(!person){const p=document.createElement('p');p.className='empty';p.textContent='Selecciona una persona para ver conexiones directas verificadas.';list.append(p);return;}
  const items=await api('/people/'+person+'/connections');
  if(!items.length){const p=document.createElement('p');p.className='empty';p.textContent='No hay conexiones verificadas para esta persona.';list.append(p);return;}
  for(const item of items){const box=document.createElement('div');box.className='record';
    const title=document.createElement('strong');title.textContent=nameFor('people',item.person_id);
    const type=document.createElement('span');
    const incoming={"family.parent_of":"Es hijo/a de","professional.mentor_of":"Recibió mentoría de"};
    type.textContent=item.direction==='incoming' && incoming[item.type_id]
      ? incoming[item.type_id] : (catalog.find(x=>x.id===item.type_id)?.label||item.type_id);
    const sources=document.createElement('small');sources.textContent='Fuentes: '+item.source_ids.map(id=>cache.sources.find(x=>x.id===id)?.title||id).join(' · ');
    const facts=document.createElement('small');facts.textContent='Hechos: '+item.fact_ids.join(', ');
    box.append(title,type,sources,facts);
    if(item.location){
      const loc=document.createElement('small');
      loc.style.color='#1b4332';
      loc.style.fontWeight='600';
      const coords=(item.location.lat!=null && item.location.lng!=null)?` (${item.location.lat.toFixed(4)}, ${item.location.lng.toFixed(4)})`:'';
      loc.textContent='📍 '+(item.location.name||item.location.city||'')+coords;
      box.append(loc);
    }
    list.append(box);}
}
async function init() {
  catalog=await api('/connection-types');populateTypes();await refreshChoices();renderEntityFields();
  await renderEntityList();
  document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>showView(button.dataset.view));
  $('collection').onchange=()=>{entityCurrent=null;$('search').value='';renderEntityFields();renderEntityList().catch(fail);};
  let searchTimer;$('search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>renderEntityList($('search').value).catch(fail),250);};
  $('entity-new').onclick=()=>{entityCurrent=null;renderEntityFields();};
  $('entity-form').onsubmit=saveEntity;
  $('supertype').onchange=updateTypes;$('type-id').onchange=()=>updateObjectOptions().catch(fail);
  $('peer-id').onchange=updatePeerRequirements;
  $('fact-new').onclick=resetFact;$('fact-form').onsubmit=saveFact;
  $('fact-verify').onclick=()=>factAction('verify');$('fact-archive').onclick=()=>factAction('archive');
  $('review-person').onchange=()=>renderConnections().catch(fail);
  $('refresh-facts').onclick=()=>refreshReview().catch(fail);
  bindSelectSearch('subject-search','subject-id',()=> 'people');
  bindSelectSearch('peer-search','peer-id',()=> 'people');
  bindSelectSearch('review-person-search','review-person',()=> 'people');
  bindSelectSearch('source-search','source-id',()=> 'sources');
  bindSelectSearch('peer-source-search','peer-source-id',()=> 'sources');
  bindSelectSearch('object-search','object-id',()=>({person:'people',organization:'organizations',
    work:'works',event:'events'})[selectedType()?.context_kind]||'people',
    item=>!selectedType()?.context_type || item.kind===selectedType().context_type);
}
init().catch(fail);
