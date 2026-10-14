const state={run:null,data:null,scenario:'A',timer:null,payload:null,busy:false,request:0};
const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number=(value,digits=1)=>Number(value??0).toLocaleString(undefined,{maximumFractionDigits:digits});
const icons=()=>window.lucide?.createIcons({attrs:{'stroke-width':1.7}});
const animate=(target,vars)=>window.gsap?.from(target,vars);
const valleyPresets={
  trishuli:{bbox:'85.28,28.10,85.42,28.29',event:'2026-08-26T02:52:00Z',snapshot:'2026-07-27T00:00:00Z'},
  deir:{bbox:'40.05,35.25,40.25,35.40',event:'2026-05-25T00:00:00Z',snapshot:'2026-05-01T00:00:00Z'}
};

async function api(path,options){
  const response=await fetch(path,options),data=await response.json();
  if(!response.ok)throw new Error(data.error||`Request failed (${response.status})`);
  return data;
}

async function init(){
  icons();
  if(window.gsap){
    gsap.from('.topbar',{y:-78,duration:.7,ease:'power3.out'});
    gsap.from('aside',{x:-45,duration:.75,delay:.15,ease:'power3.out'});
    gsap.from('.hero>*',{y:28,duration:.8,delay:.25,stagger:.1,ease:'power3.out'});
  }
  const config=await api('/api/config');
  $('#disclaimer').textContent=config.disclaimer;
  $('#snapshot').value=config.default_snapshot;
  $('#cache').value=config.default_cache;
  $('#checkpoint-option').value=config.default_model;
  await loadRuns(true);
}

async function loadRuns(selectFirst=false){
  const runs=await api('/api/runs');
  $('#run-list').innerHTML=runs.length?runs.map(run=>`<button class="run ${state.run===run.id?'selected':''}" data-id="${esc(run.id)}"><strong>${esc(run.id)}</strong><span><i class="dot ${run.state}"></i>${esc(run.state)}</span></button>`).join(''):'<p class="muted">No runs found.</p>';
  document.querySelectorAll('.run').forEach(element=>element.onclick=()=>selectRun(element.dataset.id));
  animate('.run',{x:-12,duration:.35,stagger:.05,ease:'power2.out'});
  if(selectFirst&&!state.run&&runs.length){
    const initial=runs.find(run=>run.state==='complete'&&run.id!=='demo_mock')||runs.find(run=>run.state==='complete')||runs[0];
    await selectRun(initial.id);
  }
  state.busy=runs.some(run=>run.state==='running');
  $('#run-form button[type=submit]').disabled=state.busy;
  clearTimeout(state.timer);
  if(state.busy)state.timer=setTimeout(async()=>{try{await loadRuns(false);if(state.run)await selectRun(state.run)}catch(error){$('#form-message').textContent=error.message}},2000);
}

async function selectRun(id){
  state.run=id;const request=++state.request;
  document.querySelectorAll('.run').forEach(element=>element.classList.toggle('selected',element.dataset.id===id));
  const payload=await api(`/api/runs/${encodeURIComponent(id)}`);
  if(request!==state.request)return;state.payload=payload;
  if(payload.state==='complete'||payload.state==='partial'){state.data=payload.results;render()}else{state.data=null;renderPending(payload)}
}

function renderPending(payload){
  $('#run-state').textContent=payload.state.toUpperCase();
  $('#run-title').innerHTML=`${esc(state.run)}<br><em>${payload.state==='failed'?'Analysis failed.':'Analysis in progress.'}</em>`;
  $('#run-meta').textContent=payload.state==='failed'?'This run failed. The reason is shown below.':'Waiting for the pipeline to finish.';
  $('#alerts').innerHTML=payload.error?`<div class="alert error">${esc(payload.error.message)}</div>`:'<div class="alert info">Analysis is running. Live stage updates will appear here.</div>';
  $('#metrics').innerHTML='';$('#provenance').innerHTML='';$('#limitations').innerHTML='';$('#evaluation-card').hidden=true;
  $('#hazard-table').innerHTML='';$('#exposure-table').innerHTML='';$('#downloads').innerHTML='';
  $('#details').innerHTML=`<div class="panel-kicker">RUN TELEMETRY</div><h2>Stage<br>activity</h2><pre>${esc((payload.log||[]).join('\n'))}</pre>`;
  hideMap();
}

function render(){
  const results=state.data,scenario=results.access.find(item=>item.scenario===state.scenario);
  $('#details').dataset.scenario=state.scenario;
  $('#run-state').textContent=results.is_partial?'PARTIAL ANALYSIS':results.model_version==='mock'?'SYNTHETIC TERRAIN':'COMPLETED ANALYSIS';
  $('#run-title').innerHTML=`${esc(results.run_id)}<br><em>Impact overview.</em>`;
  $('#run-meta').textContent=`Event ${new Date(results.inputs.event_datetime).toLocaleString()} · ${results.inputs.mode.toUpperCase()} MODE · ${String(results.model_version).toUpperCase()}`;
  $('#alerts').innerHTML=(results.model_version==='mock'?'<div class="alert info">Synthetic demonstration — fictional evidence for product testing.</div>':'')+(results.is_partial?'<div class="alert">Partial analysis: exposure or access is incomplete. Available hazard evidence remains visible.</div>':'')+(results.warnings||[]).map(warning=>`<div class="alert">${esc(warning)}</div>`).join('');
  const hazard=results.hazard.total_hazard_km2,exposure=results.exposure||{};
  $('#metrics').innerHTML=[
    metric('Mapped hazard',number(hazard,2),'km²','waves'),
    metric('Exposed buildings',exposure.total_exposed_buildings??'?','assets','building-2'),
    metric('Cut off',scenario?.counts.cut_off??'—','settlements','map-pin-off'),
    metric('Closed roads',scenario?number(scenario.closed_road_km,2):'—','km','route-off')
  ].join('');
  $('#details').innerHTML=`<div class="panel-kicker">FIELD INTELLIGENCE / ${state.scenario}</div><h2>Access<br>scenario ${state.scenario}</h2><p>${esc(scenario?.description||'Access results unavailable.')}</p>${scenario?`<div class="status-grid">${['connected','degraded','cut_off','unknown'].map(key=>`<div class="status-item"><span>${esc(key.replace('_',' '))}</span><strong>${scenario.counts[key]??0}</strong></div>`).join('')}</div><p class="summary-note">${scenario.closed_bridges} closed bridge(s). Unknown means there is no mapped baseline route — not that the location is safe.</p><h3>CUT-OFF SETTLEMENTS</h3><ul class="cutoff-list">${scenario.cut_off.length?scenario.cut_off.map(item=>`<li>${esc(item.name)}</li>`).join(''):'<li>None detected</li>'}</ul>`:''}`;
  $('#hazard-table').innerHTML=table(['Class','Area km²'],Object.entries(results.hazard.area_km2_by_class).map(([key,value])=>[key.replaceAll('_',' '),number(value,3)]).concat([['no observation',number(results.hazard.no_observation_km2,3)]]));
  const classes=new Set([...Object.keys(exposure.buildings_by_class||{}),...Object.keys(exposure.road_km_by_class||{}),...Object.keys(exposure.bridges_by_class||{})]);
  $('#exposure-table').innerHTML=results.exposure?table(['Class','Buildings','Road km','Bridges'],[...classes].map(key=>[key.replaceAll('_',' '),exposure.buildings_by_class[key]||0,number(exposure.road_km_by_class[key]||0,2),exposure.bridges_by_class[key]||0])):'<p class="muted">Unavailable for this partial run.</p>';
  const files=[['Situation report','sitrep.pdf'],['Hazard GeoPackage','hazard.gpkg'],[`Settlements ${state.scenario}`,`settlements_${state.scenario}.gpkg`],['Hazard GeoTIFF','hazard_class.tif'],['Results JSON','results.json'],['Downstream trace','flowpath.gpkg']];
  $('#downloads').innerHTML=files.filter(([,file])=>state.payload.downloads.includes(file)).map(([label,file])=>`<a class="download" href="/api/files/${encodeURIComponent(results.run_id)}/${file}"><span>${esc(label)}</span><i data-lucide="arrow-down-to-line"></i></a>`).join('');
  $('#attribution').innerHTML=results.attribution.map(item=>`<p>${esc(item)}</p>`).join('');
  const inputs=results.inputs;
  $('#provenance').innerHTML=table(['Input','Value'],[['Event UTC',inputs.event_datetime],['OSM snapshot UTC',inputs.osm_snapshot],['Track',`${inputs.rel_orbit} ${inputs.orbit_direction}`],['S1 backend',inputs.s1_backend],['Post lag hours',inputs.post_lag_hours],['Post scene',inputs.s1_post.id],['Pre scenes',inputs.s1_pre.map(x=>x.id).join('; ')],['S2 scenes',inputs.s2_scenes.join('; ')||'none'],['S2 clear fraction',inputs.s2_clear_fraction??'unavailable']]);
  $('#limitations').innerHTML='<ul>'+results.limitations.map(x=>`<li>${esc(x)}</li>`).join('')+'</ul>'+(results.flowpath?`<h3>Computed downstream trace</h3><p>${esc(results.flowpath.length_km)} km. Nearby places: ${esc(results.flowpath.settlements.join(', ')||'none mapped')}.</p>`:'<p>No downstream trace requested or available.</p>')+'<p>3D terrain uses this run&#39;s Copernicus DEM; coverage ends at the DEM boundary.</p>';
  const evaluation=Object.entries(state.payload.evaluation||{});$('#evaluation-card').hidden=!evaluation.length;$('#evaluation').innerHTML=evaluation.map(([name,text])=>`<h3>${esc(name)}</h3><pre>${esc(text)}</pre>`).join('');
  showMap();icons();
  animate('.metric',{y:18,duration:.55,stagger:.08,ease:'power3.out'});
  animate('.data-card',{y:24,duration:.6,stagger:.09,ease:'power3.out'});
  animate('.intel-panel>*',{x:18,duration:.45,stagger:.05,ease:'power2.out'});
}

function metric(label,value,unit,icon){return `<div class="metric"><div class="metric-top"><span>${esc(label)}</span><i data-lucide="${icon}"></i></div><strong>${esc(value)} <em>${esc(unit)}</em></strong></div>`}
function table(headers,rows){return `<table><thead><tr>${headers.map(item=>`<th>${esc(item)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(item=>`<td>${esc(item)}</td>`).join('')}</tr>`).join('')}</tbody></table>`}
function showMap(){const frame=$('#map');frame.src=`/static/map.html?run=${encodeURIComponent(state.run)}&scenario=${state.scenario}&v=${Date.now()}`;frame.style.display='block';$('#map-empty').style.display='none';animate('.map-card',{scale:.985,duration:.65,ease:'power2.out'})}
function hideMap(){$('#map').style.display='none';$('#map-empty').style.display='flex'}

document.querySelectorAll('[data-scenario]').forEach(button=>button.onclick=()=>{
  state.scenario=button.dataset.scenario;
  document.querySelectorAll('[data-scenario]').forEach(item=>item.classList.toggle('active',item===button));
  if(state.data)render();
});
$('#refresh-runs').onclick=()=>loadRuns(false);
$('#valley-preset').onchange=event=>{
  const preset=valleyPresets[event.target.value];
  if(!preset)return;
  $('#bbox').value=preset.bbox;$('#event-time').value=preset.event;$('#snapshot').value=preset.snapshot;
  $('#flow-source').value='';
  animate('#run-form input',{backgroundColor:'rgba(131,0,0,.32)',duration:.5,stagger:.04,yoyo:true,repeat:1});
};
$('#run-form').onsubmit=async event=>{
  event.preventDefault();
  const button=event.submitter,message=$('#form-message');button.disabled=true;message.textContent='INITIALIZING PIPELINE…';
  try{
    const body=Object.fromEntries(new FormData(event.target));
    const run=await api('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    message.textContent='ANALYSIS STARTED';await loadRuns(false);await selectRun(run.id);
  }catch(error){message.textContent=error.message}finally{button.disabled=state.busy}
};
init().catch(error=>{$('#server-status').textContent='LOCAL / ERROR';$('#alerts').innerHTML=`<div class="alert error">${esc(error.message)}</div>`});
