const state = {
  run: null, data: null, payload: null, scenario: 'A', runs: [], busy: false, timer: null,
  request: 0, archivePage: 0, settlementPage: 0, settlementQuery: '', settlementKind: 'cut_off',
  mapReady: false, mapRequest: 0, drawerFocus: null, mapStep: 'flood', mapMode: 'story', mapChrome: 240
};
const ARCHIVE_PAGE_SIZE = 8, SETTLEMENT_PAGE_SIZE = 4;
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = (value, digits = 1) => Number(value ?? 0).toLocaleString(undefined, {maximumFractionDigits: digits});
const icons = () => window.lucide?.createIcons({attrs: {'stroke-width': 1.7, 'aria-hidden': 'true'}});
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const valleyPresets = {
  trishuli: {bbox:'85.28,28.10,85.42,28.29',event:'2026-08-26T02:52:00Z',snapshot:'2026-07-27T00:00:00Z'},
  deir: {bbox:'40.05,35.25,40.25,35.40',event:'2026-05-25T00:00:00Z',snapshot:'2026-05-01T00:00:00Z'}
};
const hazardLabels = {
  flood_high: ['Flood · high', '#0879bd'], flood_possible: ['Flood · possible', '#80c8e7'],
  rule_decrease: ['Radar decrease · water or mud', '#cf930c'], rule_increase: ['Radar increase · roughness', '#b23b27'],
  permanent_water: ['Permanent water', '#154a82'], no_observation: ['No observation', '#727d85'],
  no_obs: ['No observation', '#727d85']
};
function dateTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('en-GB', {
    day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'UTC'
  }) + ' UTC';
}
function archiveDate(run) {
  const match = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/.exec(run.id);
  return match ? new Date(match[1]+'-'+match[2]+'-'+match[3]+'T'+match[4]+':'+match[5]+':'+match[6]+'Z') : new Date(run.modified * 1000);
}
function archiveTitle(run) {
  if (/^\d{8}T\d{6}/.test(run.id)) return archiveDate(run).toLocaleDateString('en-GB', {day:'numeric',month:'short',timeZone:'UTC'}) + ' analysis';
  return run.id.replaceAll('_', ' ').replaceAll('-', ' ').replace(/\b[a-z]/g, char => char.toUpperCase());
}
function overviewTitle(results) {
  if (results.model_version === 'mock') return 'Synthetic valley overview';
  const [west, south, east, north] = results.inputs.aoi_bbox, lon = (west + east) / 2, lat = (south + north) / 2;
  if (lon > 85 && lon < 86 && lat > 27 && lat < 29) return 'Trishuli flood overview';
  if (lon > 39.5 && lon < 41 && lat > 34.5 && lat < 36) return 'Euphrates flood overview';
  return 'Flood impact overview';
}
async function api(path, options) {
  const response = await fetch(path, options), data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed (' + response.status + ')');
  return data;
}
function notice(text, kind = '') {
  return '<div class="alert '+kind+'"><i data-lucide="'+(kind === 'error' ? 'circle-alert' : kind === 'info' ? 'info' : 'triangle-alert')+'"></i><span>'+esc(text)+'</span></div>';
}
function setPanel(panel, focus = false) {
  document.querySelectorAll('[data-panel]').forEach(button => {
    const active = button.dataset.panel === panel;
    button.classList.toggle('active', active); button.setAttribute('aria-selected', active);
    button.tabIndex = active ? 0 : -1;
  });
  $('#archive-panel').hidden = panel !== 'archive'; $('#setup-panel').hidden = panel !== 'setup';
  if (focus) (panel === 'setup' ? $('#valley-preset') : $('#run-search')).focus();
}
function setControlsOpen(open, focus = true) {
  if (open) state.drawerFocus = document.activeElement;
  document.body.classList.toggle('controls-open', open);
  $('#drawer-backdrop').hidden = !open;
  $('#controls-toggle').setAttribute('aria-expanded', open);
  $('#sidebar').setAttribute('aria-hidden', !open);
  $('#overview').inert = open;
  if (focus && open) $('#sidebar [role="tab"][aria-selected="true"]').focus();
  if (!open && focus && state.drawerFocus?.getClientRects().length) state.drawerFocus.focus();
}
function openPanel(panel) {
  setPanel(panel);
  setControlsOpen(true, false);
  (panel === 'setup' ? $('#valley-preset') : $('#run-search')).focus();
}
function filteredRuns() {
  const query = $('#run-search').value.trim().toLocaleLowerCase(), filter = $('#run-filter').value;
  return state.runs.filter(run => (filter === 'all' || run.state === filter) &&
    (run.id + ' ' + archiveTitle(run) + ' ' + dateTime(archiveDate(run))).toLocaleLowerCase().includes(query));
}
function renderArchive() {
  const runs = filteredRuns(), pages = Math.max(1, Math.ceil(runs.length / ARCHIVE_PAGE_SIZE));
  state.archivePage = Math.min(state.archivePage, pages - 1);
  const start = state.archivePage * ARCHIVE_PAGE_SIZE, visible = runs.slice(start, start + ARCHIVE_PAGE_SIZE);
  $('#run-count').textContent = state.runs.length;
  $('#run-list').innerHTML = visible.length ? visible.map(run =>
    '<button class="run '+(state.run === run.id ? 'selected' : '')+'" data-id="'+esc(run.id)+'" title="'+esc(run.id)+'" aria-pressed="'+(state.run === run.id)+'">'+
    '<div class="run-top"><strong>'+esc(archiveTitle(run))+'</strong><span class="run-state '+esc(run.state)+'"><i class="dot"></i>'+esc(run.state[0].toUpperCase()+run.state.slice(1))+'</span></div>'+
    '<span class="run-time">'+esc(dateTime(archiveDate(run)))+'</span><span class="run-id-text">'+esc(run.id)+'</span></button>'
  ).join('') : '<p class="empty-copy">'+(state.runs.length ? 'No matching runs. Try a different search or status.' : 'Your saved analyses will appear here. Start a new analysis to begin.')+'</p>';
  $('#archive-range').textContent = runs.length ? (start + 1)+'–'+Math.min(start + ARCHIVE_PAGE_SIZE, runs.length)+' of '+runs.length : '0 matching runs';
  $('#archive-prev').disabled = state.archivePage === 0; $('#archive-next').disabled = state.archivePage >= pages - 1;
  document.querySelectorAll('.run').forEach(element => element.onclick = () => {
    selectRun(element.dataset.id).catch(showError);
    setControlsOpen(false);
  });
  icons();
}
function showError(error) { $('#alerts').innerHTML = notice(error.message, 'error'); icons(); }
async function loadRuns(selectFirst = false) {
  state.runs = await api('/api/runs'); renderArchive();
  state.busy = state.runs.some(run => run.state === 'running');
  $('#run-form button[type=submit]').disabled = state.busy;
  if (selectFirst && !state.run && state.runs.length) {
    const initial = state.runs.find(run => run.state === 'complete' && run.id !== 'demo_mock') ||
      state.runs.find(run => run.state === 'complete') || state.runs[0];
    await selectRun(initial.id);
  }
  if (!state.runs.length) setPanel('setup');
  clearTimeout(state.timer);
  if (state.busy) state.timer = setTimeout(async () => {
    try {
      await loadRuns(false);
      if (state.run && ['running','incomplete'].includes(state.payload?.state)) await selectRun(state.run);
    } catch (error) { $('#form-message').textContent = error.message; }
  }, 2500);
}
async function selectRun(id) {
  state.run = id; state.settlementPage = 0; state.settlementQuery = ''; state.settlementKind = 'cut_off';
  state.data = null; state.payload = null;
  const request = ++state.request; renderArchive();
  renderPending({state:'loading'});
  $('#run-state').textContent = 'LOADING ANALYSIS';
  $('#run-title').textContent = 'Opening saved analysis…';
  $('#run-meta').textContent = 'Loading this run’s satellite evidence and results.';
  $('#map-status').textContent = 'Loading analysis…';
  $('#alerts').innerHTML = notice('Loading the selected analysis.', 'info');
  $('#details').innerHTML = '<div class="panel-kicker">SAVED ANALYSIS</div><h2>Loading evidence</h2><p class="muted">Opening the selected run’s results and settlement access.</p>';
  const payload = await api('/api/runs/'+encodeURIComponent(id));
  if (request !== state.request) return;
  state.payload = payload;
  if (['complete','partial'].includes(payload.state)) { state.data = payload.results; render(); }
  else { state.data = null; renderPending(payload); }
}
function syncScenarios() {
  document.querySelectorAll('.scenario-control button[data-scenario]').forEach(button => {
    const active = button.dataset.scenario === state.scenario;
    button.classList.toggle('active', active); button.setAttribute('aria-pressed', active);
    button.disabled = !state.data?.access.some(item => item.scenario === button.dataset.scenario);
    button.title = state.data?.access.find(item => item.scenario === button.dataset.scenario)?.description || 'Access results unavailable';
  });
}
function formatLog(line) {
  try {
    const row = JSON.parse(line);
    return (row.stage || 'pipeline')+' · '+(row.message || row.event || 'update');
  } catch { return line; }
}
function renderPending(payload) {
  $('#run-state').textContent = payload.state === 'failed' ? 'ANALYSIS FAILED' : 'ANALYSIS RUNNING';
  $('#run-state').dataset.state = payload.state;
  $('#run-title').textContent = payload.state === 'failed' ? 'This analysis needs attention.' : 'Your analysis is in progress.';
  $('#run-meta').textContent = payload.state === 'failed' ? 'The run stopped before producing complete results.' : 'Stage updates appear below. You can browse other runs while it completes.';
  $('#run-id').hidden = false; $('#run-id').textContent = 'Run · '+state.run;
  $('#quick-report').hidden = true;
  $('#alerts').innerHTML = payload.error ? notice(payload.error.message, 'error') : notice('Processing satellite evidence, terrain, and mapped infrastructure.', 'info');
  $('#metrics').innerHTML = [
    metric('Mapped hazard','—','','waves','Awaiting results'),
    metric('Exposed buildings','—','','building-2','Awaiting results'),
    metric('Cut-off settlements','—','','map-pin-off','Awaiting results'),
    metric('Closed roads','—','','route-off','Awaiting results')
  ].join('');
  for (const id of ['provenance','limitations','hazard-table','exposure-table','downloads','evaluation']) $('#'+id).innerHTML = '<p class="empty-copy">No completed result for this run.</p>';
  $('#attribution').textContent = 'Sentinel · Copernicus DEM · Pre-event OpenStreetMap';
  $('#evaluation-card').hidden = true;
  $('#details').innerHTML = '<div class="panel-kicker">RUN PROGRESS</div><h2>Stage activity</h2><p>Latest pipeline updates</p>'+
    (payload.log?.length ? '<pre>'+esc(payload.log.map(formatLog).join('\n'))+'</pre>' : '<div class="panel-empty"><i data-lucide="'+(payload.state === 'failed' ? 'circle-alert' : 'loader-circle')+'"></i><p>'+(payload.state === 'failed' ? 'Check the error above, then start a new analysis.' : 'Waiting for the first stage update.')+'</p></div>');
  hideMap(); syncScenarios(); icons();
}
function metric(label, value, unit, icon, note, danger = false) {
  return '<div class="metric '+(danger ? 'danger' : '')+'"><div class="metric-top"><span>'+esc(label)+'</span><div class="metric-icon"><i data-lucide="'+icon+'"></i></div></div>'+
    '<strong>'+esc(value)+(unit ? ' <em>'+esc(unit)+'</em>' : '')+'</strong><p>'+esc(note)+'</p></div>';
}
function classCell(name) {
  const [label, color] = hazardLabels[name] || [name.replaceAll('_',' '),'#8b98a7'];
  return {label, color};
}
function table(headers, rows) {
  return '<table><thead><tr>'+headers.map(item => '<th scope="col">'+esc(item)+'</th>').join('')+'</tr></thead><tbody>'+
    rows.map(row => '<tr>'+row.map(item => '<td>'+(typeof item === 'object' && item !== null ?
      '<span class="class-label"><i class="class-swatch" style="--class-color:'+item.color+'"></i>'+esc(item.label)+'</span>' : esc(item))+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
}
function render() {
  const results = state.data, scenario = results.access.find(item => item.scenario === state.scenario);
  $('#run-state').textContent = results.is_partial ? 'PARTIAL ANALYSIS' : results.model_version === 'mock' ? 'SYNTHETIC DEMO' : 'COMPLETED ANALYSIS';
  $('#run-state').dataset.state = results.is_partial ? 'partial' : 'complete';
  $('#run-title').textContent = overviewTitle(results);
  $('#run-meta').textContent = 'Event '+dateTime(results.inputs.event_datetime)+' · '+results.inputs.mode[0].toUpperCase()+results.inputs.mode.slice(1)+' processing · '+(results.model_version === 'b0' ? 'B0 baseline' : results.model_version === 'mock' ? 'Demo data' : results.model_version === 'cutoff_unet_v1.pt' ? 'U-Net v1' : 'U-Net model');
  $('#run-id').hidden = false; $('#run-id').textContent = 'Run · '+results.run_id;
  const available = state.payload.downloads || [];
  $('#quick-report').hidden = !available.includes('sitrep.pdf');
  $('#quick-report').href = '/api/files/'+encodeURIComponent(results.run_id)+'/sitrep.pdf';
  $('#alerts').innerHTML =
    (results.model_version === 'mock' ? notice('Synthetic demonstration. This is fictional evidence for product testing.', 'info') : '') +
    (results.is_partial ? notice('Partial analysis. Exposure or access is incomplete; available hazard evidence remains visible.') : '') +
    (results.warnings || []).map(warning => notice(warning)).join('');
  const exposure = results.exposure || {};
  $('#metrics').innerHTML = [
    metric('Mapped hazard',number(results.hazard.total_hazard_km2,2),'km²','waves','Flood + radar change evidence'),
    metric('Exposed buildings',results.exposure ? number(exposure.total_exposed_buildings,0) : '—','','building-2',results.exposure ? 'Mapped footprints in hazard' : 'Exposure unavailable'),
    metric('Cut-off settlements',scenario ? number(scenario.counts.cut_off,0) : '—','','map-pin-off','Scenario '+state.scenario+' · road access', Boolean(scenario?.counts.cut_off)),
    metric('Closed roads',scenario ? number(scenario.closed_road_km,2) : '—','km','route-off','Scenario '+state.scenario+' · inferred closures')
  ].join('');
  renderDetails(scenario);
  $('#hazard-table').innerHTML = table(['Hazard class','Area · km²'],
    Object.entries(results.hazard.area_km2_by_class).map(([key,value]) => [classCell(key),number(value,3)]).concat([[classCell('no_observation'),number(results.hazard.no_observation_km2,3)]])) +
    '<p class="card-description" style="margin-top:12px">Radar changes are not proof of floodwater. Permanent water is excluded from the hazard total.</p>';
  const classes = new Set([...Object.keys(exposure.buildings_by_class || {}),...Object.keys(exposure.road_km_by_class || {}),...Object.keys(exposure.bridges_by_class || {})]);
  $('#exposure-table').innerHTML = results.exposure ? table(['Hazard class','Buildings','Road km','Bridges'],[...classes].map(key => [
    classCell(key),number(exposure.buildings_by_class[key] || 0,0),number(exposure.road_km_by_class[key] || 0,2),number(exposure.bridges_by_class[key] || 0,0)
  ])) : '<p class="empty-copy">Exposure is unavailable for this partial run.</p>';
  const files = [
    ['Situation report','sitrep.pdf','PDF','file-text'],
    ['Hazard polygons','hazard.gpkg','GEOPACKAGE','layers'],
    ['Settlement access · '+state.scenario,'settlements_'+state.scenario+'.gpkg','GEOPACKAGE','map-pin'],
    ['Hazard raster','hazard_class.tif','GEOTIFF','image'],
    ['Complete results','results.json','JSON','file-json'],
    ['Downstream trace','flowpath.gpkg','GEOPACKAGE','route']
  ];
  $('#downloads').innerHTML = files.filter(([,file]) => available.includes(file)).map(([label,file,type,icon]) =>
    '<a class="download" href="/api/files/'+encodeURIComponent(results.run_id)+'/'+file+'"><span><i data-lucide="'+icon+'"></i><span>'+esc(label)+'<small>'+type+'</small></span></span><i data-lucide="arrow-down-to-line"></i></a>'
  ).join('') || '<p class="empty-copy">No exports are available for this run.</p>';
  $('#attribution').innerHTML = results.attribution.map(item => '<p>'+esc(item)+'</p>').join('');
  const inputs = results.inputs;
  $('#provenance').innerHTML = table(['Input','Value'],[
    ['Event UTC',inputs.event_datetime],['OSM snapshot UTC',inputs.osm_snapshot],
    ['Orbit track',inputs.rel_orbit+' · '+inputs.orbit_direction],['S1 backend',inputs.s1_backend],
    ['Post lag · hours',number(inputs.post_lag_hours,2)],['Post scene',inputs.s1_post.id],
    ['Pre scenes',inputs.s1_pre.map(item => item.id).join('; ')],['S2 scenes',inputs.s2_scenes.join('; ') || 'None'],
    ['S2 clear fraction',inputs.s2_clear_fraction ?? 'Unavailable'],['Model',results.model_version],['Analysis CRS','EPSG:'+inputs.grid_epsg]
  ]);
  $('#limitations').innerHTML = '<ul>'+results.limitations.map(item => '<li>'+esc(item)+'</li>').join('')+'</ul>' +
    (results.flowpath ? '<h3>Computed downstream trace</h3><p>'+esc(results.flowpath.length_km)+' km. Nearby places: '+esc(results.flowpath.settlements.join(', ') || 'None mapped')+'.</p>' :
      '<p>No pipeline flow trace was requested. A prepared map may include a separate local DEM trace for display.</p>') + '<p>Terrain uses this run’s Copernicus DEM. Coverage ends at the DEM boundary.</p>';
  const evaluation = Object.entries(state.payload.evaluation || {});
  $('#evaluation-card').hidden = !evaluation.length;
  $('#evaluation').innerHTML = evaluation.map(([name,text]) => '<h3>'+esc(name)+'</h3><pre>'+esc(text)+'</pre>').join('');
  syncScenarios(); showMap(); icons();
  if (!reducedMotion.matches) window.gsap?.from('.metric', {y:7,duration:.25,stagger:.03,clearProps:'all'});
}
function renderDetails(scenario) {
  $('#details').dataset.scenario = state.scenario;
  if (!scenario) {
    $('#details').innerHTML = '<div class="panel-kicker">ROAD ACCESS</div><h2>Access unavailable</h2><p>This run did not complete the infrastructure or access stages.</p><div class="panel-empty"><i data-lucide="route-off"></i><p>Available hazard evidence remains on the map.</p></div>';
    return;
  }
  $('#details').innerHTML = '<div class="panel-kicker">ROAD ACCESS · SCENARIO '+state.scenario+'</div><h2>Settlement access</h2><p>'+esc(scenario.description)+'</p>'+
    '<div class="status-grid">'+['connected','degraded','cut_off','unknown'].map(key =>
      '<div class="status-item" data-status="'+key+'"><span>'+esc(key[0].toUpperCase()+key.slice(1).replace('_',' '))+'</span><strong>'+number(scenario.counts[key] ?? 0,0)+'</strong></div>').join('')+'</div>'+
    '<p class="summary-note"><b>'+number(scenario.closed_bridges,0)+' '+(scenario.closed_bridges === 1 ? 'bridge' : 'bridges')+' closed.</b> Unknown = no mapped baseline route; safety is unverified.</p>'+
    '<div class="settlement-toolbar"><h3>Settlements to review</h3><select id="settlement-kind" aria-label="Settlement access status"><option value="cut_off">Cut off ('+scenario.cut_off.length+')</option><option value="degraded">Degraded ('+scenario.degraded.length+')</option></select></div>'+
    '<label class="search-field"><i data-lucide="search"></i><input id="settlement-search" type="search" placeholder="Search settlements…" aria-label="Search settlements"></label>'+
    '<ul class="cutoff-list" id="settlement-list" aria-label="Settlements to review"></ul>'+
    '<div class="pagination"><span id="settlement-range" aria-live="polite"></span><div><button class="icon-button" id="settlement-prev" aria-label="Previous settlements"><i data-lucide="chevron-left"></i></button><button class="icon-button" id="settlement-next" aria-label="Next settlements"><i data-lucide="chevron-right"></i></button></div></div>';
  $('#settlement-kind').value = state.settlementKind;
  $('#settlement-search').value = state.settlementQuery;
  $('#settlement-kind').onchange = event => { state.settlementKind = event.target.value; state.settlementPage = 0; renderSettlementList(); };
  $('#settlement-search').oninput = event => { state.settlementQuery = event.target.value; state.settlementPage = 0; renderSettlementList(); };
  $('#settlement-prev').onclick = () => { state.settlementPage--; renderSettlementList(); };
  $('#settlement-next').onclick = () => { state.settlementPage++; renderSettlementList(); };
  renderSettlementList();
}
function renderSettlementList() {
  const scenario = state.data?.access.find(item => item.scenario === state.scenario);
  if (!scenario || !$('#settlement-list')) return;
  const query = state.settlementQuery.trim().toLocaleLowerCase();
  const items = (scenario[state.settlementKind] || []).filter(item => (item.name+' '+item.sid).toLocaleLowerCase().includes(query));
  const pages = Math.max(1,Math.ceil(items.length / SETTLEMENT_PAGE_SIZE));
  state.settlementPage = Math.max(0,Math.min(state.settlementPage,pages - 1));
  const start = state.settlementPage * SETTLEMENT_PAGE_SIZE, visible = items.slice(start,start + SETTLEMENT_PAGE_SIZE);
  $('#settlement-list').innerHTML = visible.length ? visible.map((item,index) =>
    '<li><button class="settlement-row" data-settlement="'+index+'" title="Locate '+esc(item.name)+' on the map'+(item.t0_min != null ? ' · Baseline '+number(item.t0_min,1)+' min to a mapped target' : '')+'" '+(state.mapReady ? '' : 'disabled')+'><span><bdi dir="auto">'+esc(item.name || 'Unnamed settlement')+'</bdi></span><i data-lucide="locate-fixed"></i></button></li>'
  ).join('') : '<li class="empty-copy">'+(query ? 'No settlements match your search.' : state.settlementKind === 'cut_off' ? 'No cut-off settlements in this scenario.' : 'No degraded settlements in this scenario.')+'</li>';
  $('#settlement-range').textContent = items.length ? (start + 1)+'–'+Math.min(start + SETTLEMENT_PAGE_SIZE,items.length)+' of '+items.length : '0 settlements';
  $('#settlement-prev').disabled = state.settlementPage === 0;
  $('#settlement-next').disabled = state.settlementPage >= pages - 1;
  document.querySelectorAll('[data-settlement]').forEach(button => button.onclick = () => {
    const item = visible[Number(button.dataset.settlement)];
    if (!state.mapReady) return;
    $('#map').contentWindow.postMessage({type:'cutoff-focus-settlement',run:state.run,scenario:state.scenario,view:state.mapRequest,
      lon:item.lon,lat:item.lat,name:item.name,status:state.settlementKind,t0_min:item.t0_min},location.origin);
    $('.map-heading').scrollIntoView({behavior:reducedMotion.matches?'auto':'smooth',block:'start'});
  });
  icons();
}
function showMap() {
  state.mapReady = false; state.mapRequest++;
  const frame = $('#map');
  $('#map-status').textContent = 'Loading map…'; $('#map-status').dataset.ready = 'false';
  frame.src = '/static/'+(state.mapMode === 'terrain' ? 'terrain-map.html' : 'map.html')+'?run='+encodeURIComponent(state.run)+'&scenario='+state.scenario+'&view='+state.mapRequest+'&step='+state.mapStep;
  document.querySelectorAll('[data-map-view]').forEach(button=>{const active=button.dataset.mapView===state.mapMode;button.classList.toggle('active',active);button.setAttribute('aria-pressed',active);});
  frame.style.display = 'block'; $('#map-empty').style.display = 'none';
  document.querySelectorAll('[data-settlement]').forEach(button => button.disabled = true);
}
function hideMap() {
  state.mapReady = false; state.mapRequest++;
  $('#map').style.display = 'none'; $('#map').removeAttribute('src');
  $('#map-empty').style.display = 'flex'; $('#map-status').textContent = 'Map unavailable'; $('#map-status').dataset.ready = 'false';
}
window.addEventListener('message', event => {
  const data = event.data;
  if (event.origin !== location.origin || event.source !== $('#map').contentWindow || !data ||
      data.run !== state.run || data.scenario !== state.scenario || String(data.view) !== String(state.mapRequest)) return;
  if (data.type === 'cutoff-map-ready') {
    state.mapReady = true; $('#map-status').textContent = 'Evidence loaded'; $('#map-status').dataset.ready = 'true';
    document.querySelectorAll('[data-settlement]').forEach(button => button.disabled = false);
  }
  if (data.type === 'cutoff-map-error') { $('#map-status').textContent = 'Map could not load'; }
  if (data.type === 'cutoff-map-view' && ['before','flood','flow','access'].includes(data.step)) state.mapStep = data.step;
  if (data.type === 'cutoff-map-height' && Number.isFinite(data.chromeHeight) && data.chromeHeight >= 0 && data.chromeHeight < 1600) {
    state.mapChrome = data.chromeHeight; resizeMapFrame();
  }
});
function resizeMapFrame() {
  const canvasHeight = Math.max(innerWidth < 700 ? 460 : 600, Math.min(1000, Math.round(innerHeight * .8)));
  $('.map-viewport').style.height = (canvasHeight + state.mapChrome) + 'px';
}
window.addEventListener('resize', resizeMapFrame);
document.querySelectorAll('[data-map-view]').forEach(button=>button.addEventListener('click',()=>{
  state.mapMode=button.dataset.mapView; if(state.data)showMap();
}));
document.querySelectorAll('.scenario-control button[data-scenario]').forEach(button => button.onclick = () => {
  state.scenario = button.dataset.scenario; state.settlementPage = 0; state.settlementQuery = '';
  if (state.data) render(); else syncScenarios();
});
document.querySelectorAll('[data-panel]').forEach(button => {
  button.onclick = () => setPanel(button.dataset.panel);
  button.onkeydown = event => {
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    event.preventDefault();
    const panel = event.key === 'Home' ? 'archive' : event.key === 'End' ? 'setup' : button.dataset.panel === 'archive' ? 'setup' : 'archive';
    setPanel(panel); $('[data-panel="'+panel+'"]').focus();
  };
});
$('#new-analysis').onclick = () => openPanel('setup');
$('#empty-select-run').onclick = () => openPanel('archive');
$('#controls-toggle').onclick = () => {const archiveOpen=document.body.classList.contains('controls-open')&&!$('#archive-panel').hidden;setPanel('archive');setControlsOpen(!archiveOpen);};
$('#close-controls').onclick = () => setControlsOpen(false);
$('#drawer-backdrop').onclick = () => setControlsOpen(false);
document.addEventListener('keydown', event => {
  if (!document.body.classList.contains('controls-open')) return;
  if (event.key === 'Escape') { event.preventDefault(); setControlsOpen(false); }
  if (event.key === 'Tab') {
    const elements = [...$('#sidebar').querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),summary,a[href]')].filter(element => element.tabIndex >= 0 && element.getClientRects().length);
    const first = elements[0], last = elements.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
});
$('#run-search').oninput = () => { state.archivePage = 0; renderArchive(); };
$('#run-filter').onchange = () => { state.archivePage = 0; renderArchive(); };
$('#archive-prev').onclick = () => { state.archivePage--; renderArchive(); };
$('#archive-next').onclick = () => { state.archivePage++; renderArchive(); };
$('#refresh-runs').onclick = () => loadRuns(false).catch(showError);
$('#valley-preset').onchange = event => {
  const preset = valleyPresets[event.target.value]; if (!preset) return;
  $('#bbox').value = preset.bbox; $('#event-time').value = preset.event;
  $('#snapshot').value = preset.snapshot; $('#flow-source').value = '';
};
$('#run-form').onsubmit = async event => {
  event.preventDefault();
  const button = $('#run-form button[type=submit]'), message = $('#form-message');
  button.disabled = true; message.textContent = 'Starting the analysis…';
  try {
    const body = Object.fromEntries(new FormData(event.target));
    const run = await api('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    message.textContent = 'Analysis started. Stage updates appear in the overview.';
    state.archivePage = 0; $('#run-search').value = ''; $('#run-filter').value = 'all';
    await loadRuns(false); await selectRun(run.id); setPanel('archive');
    setControlsOpen(false);
    $('#overview').scrollIntoView({behavior:reducedMotion.matches ? 'instant' : 'smooth',block:'start'});
  } catch (error) { message.textContent = error.message; }
  finally { button.disabled = state.busy; }
};
async function init() {
  icons(); setPanel('archive'); syncScenarios();
  const config = await api('/api/config');
  $('#disclaimer').textContent = config.disclaimer;
  $('#snapshot').value = config.default_snapshot; $('#cache').value = config.default_cache;
  $('#checkpoint-option').value = config.default_model;
  const full = $('input[name=mode][value=full]'); full.disabled = Boolean(config.full_mode_unavailable);
  if (full.disabled) {
    full.closest('label').title = config.full_mode_unavailable;
    full.closest('label').querySelector('small').textContent = 'Setup needed';
  }
  await loadRuns(true);
}
init().catch(error => { $('#server-status').textContent = 'Connection error'; showError(error); });
