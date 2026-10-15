const params=new URLSearchParams(location.search);
const run=params.get('run'),scenario=params.get('scenario')||'A';
const state=document.getElementById('map-state');
const statusColors={connected:'#17775f',degraded:'#d89513',cut_off:'#c93131',unknown:'#788492'};
const layerGroups={hazard:['mapped-water-area','mapped-water-line','flood','permanent'],changes:['changes'],flow:['flow-base','flow-line','flow-particle-glow','flow-particles'],access:['closed-roads'],assets:['roads','exposed-roads','exposed-buildings','settlements'],contours:['contours'],no_observation:['no_observation'],score:['score'],s2:['s2']};
const escapeHtml=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

function setTerrainScale(map,exaggeration){
  map.setTerrain({source:'terrain',exaggeration});
  // The pinned local MapLibre build uses a 128-cell mesh per terrain tile.
  // Its mesh spacing can be much coarser than the elevation texture. More
  // samples reduce faceting without inventing extra height detail. The pinned
  // renderer uses Uint16 triangle indices: 256 cells plus border skirts exceed
  // 65,535 vertices and wrap indices, producing long diagonal rendering seams.
  // 192 cells including every skirt stay safely within that index capacity.
  // There is no public quality setting in this build, so guard this extension.
  const renderer=map.terrain;
  if(renderer&&renderer.meshSize===128&&Object.keys(renderer._meshCache||{}).length===0)renderer.meshSize=192;
}

function addGeo(map,id,data,type,paint,before){
  if(!data?.features?.length)return;
  map.addSource(id,{type:'geojson',data});
  map.addLayer({id,type,source:id,paint},before);
}
function popupHtml(properties){
  const title=properties.name||properties.highway||(properties.seg_id!==undefined?'Mapped road segment':'Mapped feature');
  const labels={status:'Road access',t0_min:'Before travel time (min)',t1_min:'After travel time (min)',trail_access:'Possible trail access',class_name:'Evidence class',closed:'Inferred closure',anchor_method:'Location reference',road_snap_m:'Distance to mapped road node (m)',hazard_pixel_class:'Evidence class at marker'};
  const classes={0:'No classified hazard',1:'Flood · high confidence',2:'Flood · possible',3:'Radar decrease · water or mud',4:'Radar increase · roughness',5:'Persistent water',254:'No observation'};
  const fields=Object.entries(properties).filter(([k,v])=>v!==null&&v!==''&&labels[k]);
  const note=properties.status==='cut_off'?'No route remains to the mapped destinations under this scenario. This is not proof that this settlement is underwater.':properties.status==='unknown'?'No mapped baseline route. Safety is unverified.':'';
  const observation=properties.hazard_pixel_class===254?'<p>No valid satellite observation at this point. Flooding here cannot be assessed.</p>':typeof properties.observed_flood_at_point==='boolean'?`<p>Satellite flood classification at this point: ${properties.observed_flood_at_point?'yes (not ground verified)':'none'}. A point does not describe the whole settlement.</p>`:'';
  const snap=Number(properties.road_snap_m)>100?'<p>The nearest-node road connection is inferred. A passable path from the settlement to that road has not been verified.</p>':'';
  const closure=properties.closed?`<p>Scenario ${escapeHtml(scenario)} assumes this road is closed based on ${scenario==='A'?'proximity to any hazard class, including radar changes':scenario==='B'?'sustained high-confidence hazard overlap or bridge approaches':'high-confidence hazards at bridge approaches'}. Ground passability has not been checked.</p>`:'';
  return `<strong dir="auto">${escapeHtml(title)}</strong>${fields.map(([k,v])=>{const value=k==='hazard_pixel_class'?classes[v]??v:['t0_min','t1_min'].includes(k)&&Number.isFinite(Number(v))?Number(v).toFixed(1):String(v).replaceAll('_',' ');return `<p>${labels[k]}: ${escapeHtml(value)}</p>`;}).join('')}${note?`<p>${note}</p>`:''}${observation}${snap}${closure}`;
}
function setupLayerControls(map,flow){
  window.lucide?.createIcons({'stroke-width':1.8});
  document.querySelectorAll('[data-layer]').forEach(button=>button.addEventListener('click',()=>{
    button.classList.toggle('active');
    button.setAttribute('aria-pressed',button.classList.contains('active'));
    const visibility=button.classList.contains('active')?'visible':'none';
    layerGroups[button.dataset.layer].forEach(id=>{if(map.getLayer(id))map.setLayoutProperty(id,'visibility',visibility)});
    if(['score','hazard'].includes(button.dataset.layer)&&map.getLayer('flood')){
      const scoreOn=document.querySelector('[data-layer="score"]').classList.contains('active');
      const floodOn=document.querySelector('[data-layer="hazard"]').classList.contains('active');
      map.setLayoutProperty('flood','visibility',floodOn&&!scoreOn?'visible':'none');
      document.getElementById('score-note').hidden=!scoreOn;
    }
    if(button.dataset.layer==='flow'&&visibility==='visible'){
      const coordinates=flow?.features?.flatMap(feature=>feature.geometry?.type==='LineString'?feature.geometry.coordinates:[])||[];
      // Keep the camera inside observed context: the complete downstream trace
      // can extend well beyond this case's available elevation surface.
    }
  }));
}
function animateFlow(map,collection){
  if(typeof matchMedia==='function'&&matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  const feature=collection?.features?.find(item=>item.geometry?.type==='LineString');
  const coordinates=feature?.geometry?.coordinates;
  if(!coordinates||coordinates.length<2)return;
  const particles={type:'FeatureCollection',features:[]};
  map.addSource('flow-particles',{type:'geojson',data:particles});
  map.addLayer({id:'flow-particle-glow',type:'circle',source:'flow-particles',paint:{'circle-radius':5,'circle-color':'#dc8a26','circle-opacity':.12,'circle-blur':.6,'circle-pitch-alignment':'map'}});
  map.addLayer({id:'flow-particles',type:'circle',source:'flow-particles',paint:{'circle-radius':2.5,'circle-color':'#fff1c9','circle-stroke-color':'#bb6b16','circle-stroke-width':1,'circle-pitch-alignment':'map'}});
  const started=performance.now(),count=Math.min(16,Math.max(7,coordinates.length));
  function frame(now){
    const phase=(Math.max(0,now-started)/6500)%1;
    particles.features=Array.from({length:count},(_,index)=>{
      const position=((phase+index/count)%1)*(coordinates.length-1),segment=Math.min(coordinates.length-2,Math.floor(position)),mix=position-segment;
      const a=coordinates[segment],b=coordinates[segment+1];
      return {type:'Feature',properties:{},geometry:{type:'Point',coordinates:[a[0]+(b[0]-a[0])*mix,a[1]+(b[1]-a[1])*mix]}};
    });
    map.getSource('flow-particles')?.setData(particles);requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
async function boot(){
  if(!run)throw new Error('Missing run id');
  const response=await fetch(`/api/map-data/${encodeURIComponent(run)}?scenario=${scenario}`);
  if(!response.ok)throw new Error((await response.json()).error||'Map data unavailable');
  const data=await response.json(),[w,s,e,n]=data.bounds;
  const sources={},layers=[{id:'background',type:'background',paint:{'background-color':'#c8d1ce'}}];
  if(data.terrain_url){
    const dem={type:'raster-dem',tiles:[location.origin+data.terrain_url],tileSize:512,encoding:'mapbox',minzoom:10,maxzoom:14,attribution:'Copernicus GLO-30 · native 30 m surface'};
    if(data.terrain?.bounds)dem.bounds=data.terrain.bounds;
    sources.terrain=dem;sources['terrain-light']={...dem};
  }
  const map=new maplibregl.Map({container:'map',center:[(w+e)/2,(s+n)/2],zoom:11,minZoom:11,pitch:0,bearing:0,maxPitch:65,antialias:true,style:{version:8,sources,layers}});
  // Keep the terrain camera near the study, well inside the measured 40 km context.
  if(data.terrain?.bounds)map.setMaxBounds([[w-.12,s-.12],[e+.12,n+.12]]);
  window.cutoffMap=map;
  window.addEventListener('message',event=>{
    const message=event.data;
    if(event.origin!==location.origin||event.source!==parent||message?.type!=='cutoff-focus-settlement'||message.run!==run||message.scenario!==scenario||String(message.view)!==params.get('view')||!Number.isFinite(message.lon)||!Number.isFinite(message.lat)||Math.abs(message.lon)>180||Math.abs(message.lat)>90)return;
    map.easeTo({center:[message.lon,message.lat],zoom:Math.max(map.getZoom(),14),duration:matchMedia('(prefers-reduced-motion: reduce)').matches?0:600});
    const feature=data.vectors.settlements?.features?.find(f=>f.properties.sid===message.sid||Math.abs(f.geometry.coordinates[0]-message.lon)<1e-6&&Math.abs(f.geometry.coordinates[1]-message.lat)<1e-6);
    new maplibregl.Popup({maxWidth:'320px'}).setLngLat([message.lon,message.lat]).setHTML(popupHtml({...message,...feature?.properties})).addTo(map);
  });
  map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),'top-right');
  map.addControl(new maplibregl.FullscreenControl(),'top-right');
  map.addControl(new maplibregl.ScaleControl({maxWidth:110,unit:'metric'}),'bottom-left');
  map.on('load',()=>{
    if(data.terrain_url)setTerrainScale(map,1);
    for(const name of ['terrain_relief','before_rgb','after_rgb','pre','post']){
      const layer=data.layers[name];if(!layer)continue;
      const [[south,west],[north,east]]=layer.bounds;
      map.addSource(name,{type:'image',url:layer.url,coordinates:[[west,north],[east,north],[east,south],[west,south]]});
      map.addLayer({id:name,type:'raster',source:name,layout:{visibility:name===(data.layers.terrain_relief?'terrain_relief':'pre')?'visible':'none'},paint:{'raster-opacity':1,'raster-fade-duration':0}});
    }
    if(data.terrain_url)map.addLayer({id:'terrain-shade',type:'hillshade',source:'terrain-light',paint:{'hillshade-shadow-color':'#36434a','hillshade-highlight-color':'#ffffff','hillshade-accent-color':'#727664','hillshade-exaggeration':.55,'hillshade-illumination-anchor':'map','hillshade-illumination-direction':315}});
    const water=data.vectors.river_context;
    if(water?.features?.length){
      map.addSource('mapped-water',{type:'geojson',data:water});
      map.addLayer({id:'mapped-water-area',type:'fill',source:'mapped-water',filter:['==',['geometry-type'],'Polygon'],paint:{'fill-color':'#468db1','fill-opacity':.65}});
      map.addLayer({id:'mapped-water-line',type:'line',source:'mapped-water',filter:['==',['geometry-type'],'LineString'],paint:{'line-color':'#327ea8','line-width':['interpolate',['linear'],['zoom'],11,1.2,15,3],'line-opacity':.85}});
    }
    for(const name of ['score','s2','flood','changes','permanent','no_observation']){
      const layer=data.layers[name];if(!layer)continue;
      const [[south,west],[north,east]]=layer.bounds;
      map.addSource(name,{type:'image',url:layer.url,coordinates:[[west,north],[east,north],[east,south],[west,south]]});
      map.addLayer({id:name,type:'raster',source:name,layout:{visibility:['flood','permanent','no_observation'].includes(name)?'visible':'none'},paint:{'raster-opacity':.8,'raster-fade-duration':0}});
    }
    addGeo(map,'contours',data.vectors.contours,'line',{'line-color':'#655f50','line-width':['case',['get','index'],.8,.4],'line-opacity':.38});
    if(map.getLayer('contours'))map.setLayoutProperty('contours','visibility','none');
    addGeo(map,'roads',data.vectors.roads,'line',{'line-color':'#657080','line-width':['interpolate',['linear'],['zoom'],11,.35,15,1.2],'line-opacity':.45});
    addGeo(map,'exposed-roads',data.vectors.exposed_roads,'line',{'line-color':'#cb941b','line-width':['interpolate',['linear'],['zoom'],11,1,15,2],'line-opacity':.75});
    // Footprint dimensions come from OSM. No height is available to extrude.
    addGeo(map,'exposed-buildings',data.vectors.exposed_buildings,'fill',{'fill-color':'#bc782b','fill-opacity':.45,'fill-outline-color':'#80521e'});
    addGeo(map,'closed-roads',data.vectors.closed_roads,'line',{'line-color':'#cb3537','line-width':['interpolate',['linear'],['zoom'],11,1.4,15,2.8],'line-opacity':.95});
    const flow=data.vectors.flowpath||data.vectors.context_flow;
    addGeo(map,'flow-base',flow,'line',{'line-color':'#fff7db','line-width':4,'line-opacity':.7});
    addGeo(map,'flow-line',flow,'line',{'line-color':'#b56f1e','line-width':2,'line-opacity':.95,'line-dasharray':[2,1.2]});
    animateFlow(map,flow);
    if(data.vectors.settlements?.features?.length){map.addSource('settlements',{type:'geojson',data:data.vectors.settlements});map.addLayer({id:'settlements',type:'circle',source:'settlements',paint:{'circle-radius':['interpolate',['linear'],['zoom'],11,6,15,8],'circle-color':['match',['get','status'],...Object.entries(statusColors).flat(),'#fff'],'circle-stroke-color':'#fff','circle-stroke-width':1.3,'circle-pitch-alignment':'map','circle-pitch-scale':'map'}})}
    if(map.getLayer('no_observation'))map.moveLayer('no_observation');
    setupLayerControls(map,flow);
    const background=document.getElementById('terrain-background');
    for(const option of background.options){if(!map.getLayer(option.value))option.disabled=true;}
    background.value=data.layers.terrain_relief?'terrain_relief':'pre';
    background.addEventListener('change',()=>{
      for(const id of ['terrain_relief','before_rgb','after_rgb','pre','post'])if(map.getLayer(id))map.setLayoutProperty(id,'visibility',id===background.value?'visible':'none');
      if(map.getLayer('terrain-shade'))map.setPaintProperty('terrain-shade','hillshade-exaggeration',background.value==='terrain_relief'?.55:.18);
      document.getElementById('background-note').textContent={terrain_relief:'Elevation colours show landform; they are not a satellite photograph.',before_rgb:'Dated pre-event Sentinel-2 natural colour. Clouds remain visible.',after_rgb:'Dated post-event Sentinel-2 natural colour. Clouds remain visible.',pre:'Original pre-event Sentinel-1 radar intensity. Brightness is backscatter, not elevation.',post:'Original post-event Sentinel-1 radar intensity. Brightness is backscatter, not elevation.'}[background.value];
    });
    document.getElementById('terrain-scale').addEventListener('change',event=>setTerrainScale(map,Number(event.target.value)));
    const terrain=data.terrain;
    document.getElementById('source-note').textContent=terrain?.native_resolution_m?`Copernicus GLO-30 · ${terrain.native_resolution_m} m native detail · 40 km elevation context · ${terrain.contour_interval_m} m contours. Buildings are measured footprints; heights are unavailable. Scale starts at 1×. This surface is not event-dated.`:'Cropped Copernicus GLO-30 surface; wider reviewed terrain is available in Saved runs.';
    document.getElementById('registration-note').textContent=terrain?.scenarios?.[scenario]?.markers_equal_analysis_coordinates?`Scenario ${scenario}: settlement coordinates checked against analysis; closure lines checked against pre-event OSM centre lines. Road snapping and the satellite class at each marker are in its popup.`:'Choose a terrain review run for the full registration audit.';
    document.querySelectorAll('[data-layer]').forEach(button=>{if(!layerGroups[button.dataset.layer].some(id=>map.getLayer(id))){button.disabled=true;button.title='This run has no data for this layer';}});
    function resetTerrain(){map.fitBounds([[w,s],[e,n]],{padding:55,duration:0});map.jumpTo({pitch:50,bearing:-18,zoom:Math.max(11,map.getZoom()-.2)});}
    resetTerrain();document.getElementById('reset-view').addEventListener('click',resetTerrain);
    document.getElementById('top-view').addEventListener('click',()=>map.easeTo({pitch:0,bearing:0,duration:matchMedia('(prefers-reduced-motion: reduce)').matches?0:500}));
    const required=[background.value,'flood','no_observation'].filter(name=>data.layers[name]);
    let ready=false;
    function evidenceReady(){
      if(ready||!required.every(name=>map.isSourceLoaded(name))||(data.terrain_url&&!map.isSourceLoaded('terrain')))return;
      ready=true;map.off('sourcedata',evidenceReady);state.remove();
      parent.postMessage({type:'cutoff-map-ready',run,scenario,view:params.get('view')},location.origin);
    }
    map.on('sourcedata',evidenceReady);evidenceReady();
  });
  map.on('click',event=>{const features=map.queryRenderedFeatures(event.point,{layers:['settlements','closed-roads','exposed-roads','exposed-buildings'].filter(id=>map.getLayer(id))});if(features.length){const feature=features.find(f=>f.layer.id==='settlements')||features[0];new maplibregl.Popup({closeButton:true,maxWidth:'320px'}).setLngLat(feature.geometry.type==='Point'?feature.geometry.coordinates:event.lngLat).setHTML(popupHtml(feature.properties)).addTo(map)}});
  map.on('mouseenter','settlements',()=>map.getCanvas().style.cursor='pointer');map.on('mouseleave','settlements',()=>map.getCanvas().style.cursor='');
}
boot().catch(error=>{state.textContent=error.message;parent.postMessage({type:'cutoff-map-error',run,scenario,view:params.get('view')},location.origin)});
