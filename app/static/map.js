const params=new URLSearchParams(location.search);
const run=params.get('run'),scenario=params.get('scenario')||'A';
const state=document.getElementById('map-state');
const statusColors={connected:'#22a88a',degraded:'#e8a72c',cut_off:'#df493f',unknown:'#9aabb7'};
const layerGroups={changes:['changes'],s2:['s2','after_water'],assets:['exposed-roads','exposed-buildings'],no_observation:['no_observation'],pre:['pre'],post:['post']};
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const shortDate=value=>value?new Date(value).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}):'Unavailable';
function addGeo(map,id,data,type,paint,filter){
  if(!data?.features?.length)return;
  map.addSource(id,{type:'geojson',data});
  map.addLayer({id,type,source:id,paint,...(filter?{filter}:{})});
}
function popupHtml(properties){
  const names={t0_min:'Before · minutes to a mapped target',t1_min:'After · minutes to a mapped target',status:'Road connection',trail_access:'Trail connection',class_name:'Evidence class',closed:'Inferred road closure',waterway:'Mapped waterway'};
  const fields=Object.entries(properties).filter(([k,v])=>v!==null&&v!==''&&Object.hasOwn(names,k));
  return `<strong>${escapeHtml(properties.name||properties.highway||'Mapped feature')}</strong>${fields.map(([k,v])=>`<p>${names[k]}: ${escapeHtml(String(v).replaceAll('_',' '))}</p>`).join('')}`;
}
function animateFlow(map,collection){
  if(typeof matchMedia==='function'&&matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  const feature=collection?.features?.find(item=>item.geometry?.type==='LineString');
  const coordinates=feature?.geometry?.coordinates;
  if(!coordinates||coordinates.length<2)return;
  const particles={type:'FeatureCollection',features:[]};
  map.addSource('flow-particles',{type:'geojson',data:particles});
  map.addLayer({id:'flow-particle-glow',type:'circle',source:'flow-particles',paint:{'circle-radius':7,'circle-color':'#1dc1db','circle-opacity':.25,'circle-blur':.5}});
  map.addLayer({id:'flow-particles',type:'circle',source:'flow-particles',paint:{'circle-radius':3,'circle-color':'#e1fbff','circle-stroke-color':'#007a9b','circle-stroke-width':1}});
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
  const analysis=data.analysis||{},inputs=analysis.inputs||{},observations=data.display?.observations||{};
  const flow=data.vectors.flowpath||data.vectors.context_flow;
  const floodFeatures=(data.vectors.hazard_polygons?.features||[]).filter(feature=>[1,2].includes(Number(feature.properties?.class)));
  const floodPoints={type:'FeatureCollection',features:floodFeatures.map(feature=>{
    const ring=feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates[0][0]:feature.geometry.coordinates[0];
    return {type:'Feature',properties:{...feature.properties,name:'Flood evidence patch',class_name:Number(feature.properties.class)===1?'High-confidence flood':'Possible flood'},geometry:{type:'Point',coordinates:ring[0]}};
  })};
  function baseStyle(){return {version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#d9e2d6'}}]};}
  function addHistoricalContext(target){
    target.addSource('context',{type:'raster',tiles:[location.origin+'/api/context/2025/{z}/{x}/{y}.jpg'],tileSize:256,maxzoom:15,attribution:'<a href="https://cloudless.eox.at/">EOxCloudless</a> by <a href="https://eox.at/">EOX IT Services GmbH</a> (Contains modified Copernicus Sentinel data 2025); CC BY-NC-SA 4.0'});
    const before=target.getStyle().layers.find(layer=>layer.id!=='background')?.id;
    target.addLayer({id:'historical-context',type:'raster',source:'context',paint:{'raster-opacity':.9,'raster-saturation':-.15}},before);
    // Optional context does not gate evidence readiness. Keep successful tiles
    // when one remote tile fails; deleting the whole source left the full-route
    // view blank after an unrelated tile timeout.
  }
  const map=new maplibregl.Map({container:'map',center:[(w+e)/2,(s+n)/2],zoom:10,pitch:0,bearing:0,maxPitch:0,antialias:true,style:baseStyle()});
  window.cutoffMap=map;
  map.addControl(new maplibregl.NavigationControl({showCompass:true}),'top-right');
  map.addControl(new maplibregl.FullscreenControl(),'top-right');
  map.addControl(new maplibregl.ScaleControl({maxWidth:100,unit:'metric'}),'bottom-right');
  let step=['before','flood','flow','access'].includes(params.get('step'))?params.get('step'):'flood',comparison=false,model=false,beforeMap=null,beforeReady=false,opticalMode='auto';
  const extras=new Set(['no_observation']);
  const labels=[],beforeLabels=[];
  const swatch=(color,label,type='')=>`<span><i class="${type}" style="--c:${color}"></i>${label}</span>`;
  function visibility(id,shown,target=map){if(target.getLayer(id))target.setLayoutProperty(id,'visibility',shown?'visible':'none');}
  function fitStudy(){map.fitBounds([[w,s],[e,n]],{padding:{top:64,bottom:72,left:30,right:38},duration:0});}
  function addRaster(target,name,shown=false,opacity=1){
    const layer=data.layers[name];if(!layer)return;
    const [[south,west],[north,east]]=layer.bounds;
    target.addSource(name,{type:'image',url:layer.url,coordinates:[[west,north],[east,north],[east,south],[west,south]]});
    target.addLayer({id:name,type:'raster',source:name,layout:{visibility:shown?'visible':'none'},paint:{'raster-opacity':opacity,'raster-fade-duration':0}});
  }
  function addContext(target,collection){
    const river=collection?.features||[];
    addGeo(target,'river-areas',{type:'FeatureCollection',features:river.filter(f=>['Polygon','MultiPolygon'].includes(f.geometry?.type))},'fill',{'fill-color':'#174f7e','fill-opacity':.65});
    addGeo(target,'river-lines',{type:'FeatureCollection',features:river.filter(f=>['LineString','MultiLineString'].includes(f.geometry?.type))},'line',{'line-color':['match',['get','waterway'],'river','#256899','stream','#47779d','#83a4b1'],'line-width':['interpolate',['linear'],['zoom'],9,['match',['get','waterway'],'river',1,.2],13,['match',['get','waterway'],'river',2.3,.65],17,['match',['get','waterway'],'river',4,1.5]],'line-opacity':.8});
    addGeo(target,'roads',data.vectors.roads,'line',{'line-color':'#f1e4c6','line-width':['interpolate',['linear'],['zoom'],9,.25,13,.6,17,1.8],'line-opacity':.5});
    const outline={type:'FeatureCollection',features:[{type:'Feature',properties:{},geometry:{type:'LineString',coordinates:[[w,s],[w,n],[e,n],[e,s],[w,s]]}}]};
    addGeo(target,'study-boundary',outline,'line',{'line-color':'#fcfbeb','line-width':1.1,'line-opacity':.8,'line-dasharray':[4,3]});
  }
  function updateLabels(target,items){
    const occupied=[];
    for(const item of items){
      const point=target.project(item.coordinate),width=target.getContainer().clientWidth,height=target.getContainer().clientHeight;
      const rect={x:point.x-45,y:point.y-12};
      const visible=target.getZoom()>=(item.minZoom||0)&&point.x>45&&point.x<width-45&&point.y>70&&point.y<height-90&&!occupied.some(r=>Math.abs(r.x-rect.x)<100&&Math.abs(r.y-rect.y)<27);
      item.element.style.display=visible?'':'none';if(visible)occupied.push(rect);
    }
  }
  function addLabels(target,items){
    const places=(data.vectors.places?.features||[]).filter(f=>f.geometry?.type==='Point'&&f.properties?.name&&['city','town','village','hamlet'].includes(f.properties.place));
    places.sort((a,b)=>['city','town','village','hamlet'].indexOf(a.properties.place)-['city','town','village','hamlet'].indexOf(b.properties.place));
    for(const feature of places.slice(0,120)){
      const element=document.createElement('span');element.className='place-label';element.textContent=feature.properties.name;
      new maplibregl.Marker({element,anchor:'bottom',offset:[0,-4]}).setLngLat(feature.geometry.coordinates).addTo(target);
      items.push({coordinate:feature.geometry.coordinates,element});
    }
    const named=(data.vectors.river_context?.features||[]).filter(f=>f.properties.name&&f.geometry?.type==='LineString');
    const names=new Set();
    for(const feature of named){
      const name=feature.properties.name;if(names.has(name))continue;names.add(name);
      const coordinate=feature.geometry.coordinates[Math.floor(feature.geometry.coordinates.length/2)];
      if(coordinate[0]<w||coordinate[0]>e||coordinate[1]<s||coordinate[1]>n)continue;
      const element=document.createElement('span');element.className='river-label';element.textContent=name;
      new maplibregl.Marker({element}).setLngLat(coordinate).addTo(target);items.unshift({coordinate,element,minZoom:feature.properties.waterway==='river'?0:12.5});
    }
    target.on('move',()=>updateLabels(target,items));updateLabels(target,items);
  }
  function divider(){
    const fraction=document.getElementById('divider').value;
    document.getElementById('before-clip').style.clipPath=`inset(0 ${100-fraction}% 0 0)`;
    document.getElementById('comparison-line').style.left=fraction+'%';
  }
  function syncBefore(){if(beforeReady)beforeMap.jumpTo({center:map.getCenter(),zoom:map.getZoom(),bearing:map.getBearing(),pitch:0});}
  function ensureBefore(){
    if(beforeMap)return;
    beforeMap=new maplibregl.Map({container:'before-map',interactive:false,attributionControl:false,center:map.getCenter(),zoom:map.getZoom(),pitch:0,bearing:0,style:baseStyle()});
    beforeMap.on('load',()=>{
      addRaster(beforeMap,data.layers.before_rgb?'before_rgb':'pre',true);
      addRaster(beforeMap,'before_water',true,.65);addRaster(beforeMap,'before_cloud',true,.3);
      addContext(beforeMap,data.vectors.river_context);addLabels(beforeMap,beforeLabels);
      addHistoricalContext(beforeMap);
      beforeReady=true;beforeMap.resize();syncBefore();
    });
  }
  function updateView(){
    const before=step==='before',phase=before?'before':'after';
    const useClearContext=!before&&!comparison&&data.layers.before_rgb&&(opticalMode==='before'||(opticalMode==='auto'&&observations.after?.clear_fraction_context<.5));
    const backgroundPhase=useClearContext?'before':phase;
    for(const name of ['before_rgb','after_rgb','before_water','after_water','before_cloud','after_cloud','pre','post','flood','permanent','score','s2','changes','no_observation'])visibility(name,false);
    const rgb=backgroundPhase+'_rgb',fallback=before?'pre':'post';
    visibility(data.layers[rgb]?rgb:fallback,true);
    visibility(backgroundPhase+'_cloud',true);
    if(before)visibility('before_water',true);
    else{visibility('permanent',true);visibility('flood',!model);visibility('score',model);}
    for(const [name,ids] of Object.entries(layerGroups)){
      if(name==='pre'||name==='post')continue;
      const shown=extras.has(name)&&(!before||name==='pre');
      ids.forEach(id=>visibility(id,shown));
    }
    // Radar backgrounds are exclusive; the most recent selection is explicit.
    if(extras.has('post')&&!before){visibility('post',true);visibility('pre',false);visibility('before_rgb',false);visibility('after_rgb',false);}
    else if(extras.has('pre')){visibility('pre',true);visibility('before_rgb',false);visibility('after_rgb',false);visibility('post',false);}
    ['flow-base','flow-line','flow-particle-glow','flow-particles'].forEach(id=>visibility(id,step==='flow'));
    visibility('flood-detections',!before&&!model&&step!=='access');
    ['closed-roads','closed-casing','settlements'].forEach(id=>visibility(id,step==='access'));
    document.querySelectorAll('[data-step]').forEach(button=>{const active=button.dataset.step===step;button.classList.toggle('active',active);button.setAttribute('aria-pressed',active);});
    document.querySelectorAll('[data-layer]').forEach(button=>{const active=extras.has(button.dataset.layer);button.classList.toggle('active',active);button.setAttribute('aria-pressed',active);});
    document.getElementById('model-toggle').classList.toggle('active',model);document.getElementById('model-toggle').setAttribute('aria-pressed',model);
    document.getElementById('model-card').hidden=!model;
    document.getElementById('trace-overview').hidden=step!=='flow'||!flow?.features?.length;
    document.getElementById('inspect-flood').hidden=before||model;
    document.getElementById('compare-toggle').classList.toggle('active',comparison);document.getElementById('compare-toggle').setAttribute('aria-pressed',comparison);
    for(const id of ['before-clip','before-label','comparison-line','comparison-slider'])document.getElementById(id).hidden=!comparison;
    document.body.classList.toggle('comparing',comparison);
    if(comparison){ensureBefore();beforeMap.resize();syncBefore();divider();}
    const radarOverride=extras.has('pre')?'pre':extras.has('post')&&!before?'post':null;
    const optical=radarOverride?null:observations[backgroundPhase],sensor=optical?'Sentinel-2 natural color':'Sentinel-1 VV · radar';
    const date=optical?.date||((radarOverride==='pre'||before)?inputs.s1_pre?.[0]?.datetime:inputs.s1_post?.datetime);
    document.getElementById('scene-label').innerHTML=useClearContext&&!radarOverride?`<strong>AFTER ANALYSIS · ${escapeHtml(shortDate(inputs.s1_post?.datetime))}</strong><span>Before S2 context · ${escapeHtml(shortDate(date))} · After photo ${Math.round((observations.after?.clear_fraction_context||0)*100)}% clear</span>`:`<strong>${radarOverride==='pre'?'BEFORE RADAR':before?'BEFORE':'AFTER'} · ${escapeHtml(shortDate(date))}</strong><span>${sensor}${optical?' · '+Math.round(optical.clear_fraction_context*100)+'% clear context':''}${radarOverride==='pre'&&!before?' · Event evidence overlaid':''}</span>`;
    document.getElementById('before-label').innerHTML=`<strong>BEFORE · ${escapeHtml(shortDate(observations.before?.date||inputs.s1_pre?.[0]?.datetime))}</strong><span>${observations.before?'Sentinel-2 natural color':'Sentinel-1 radar'}</span>`;
    const floodArea=(analysis.hazard?.area_km2_by_class?.flood_high||0)+(analysis.hazard?.area_km2_by_class?.flood_possible||0);
    const localFlow=!!data.vectors.context_flow&&!data.vectors.flowpath;
    const descriptions={
      before:['Before the event: find the river','Dark blue marks pre-event optical water or dated OSM waterways. The dashed outline is the study area; no event impact is shown.'],
      flood:[`${floodArea.toFixed(3)} km² of flood-specific evidence`,`Bright blue marks high-confidence flood, pale blue possible flood. Deep blue is persistent water; river outlines are pre-event OSM context. Radar changes under More layers are not proof of water.`],
      flow:['Follow the terrain downstream',flow?.features?.length?`${localFlow?'Local':'Computed'} DEM trace: animated dots show downstream direction only, not flood speed or arrival time. ${localFlow?'The local trace ends at the DEM boundary.':'Trace extent can exceed the satellite study area.'}`:'No downstream trace is available for this run. River lines remain geographic context; they are not simulated flood propagation.'],
      access:[`Road connection after the event · scenario ${scenario}`,'Red segments are inferred closures under the selected assumptions. Settlement colors show connection to a mapped target; click for before/after travel times. Exposure is not confirmed damage.']
    };
    let [title,description]=descriptions[step];
    if(model){
      title='What the AI predicts: probability of floodwater';description=`Blue intensity is the calibrated U-Net flood probability before gating. Decision threshold ${analysis.hazard?.flood_threshold??'unavailable'}; global calibration does not establish local accuracy.`;
      if(analysis.model_version==='b0'){title='B0 baseline: rule-derived flood score';description='Blue intensity is a rule-derived score, not a trained-model probability. The Flood extent view applies the analysis gates.';}
      if(analysis.model_version==='mock'){title='Synthetic demonstration score';description='Fictional evidence for product testing; not real satellite observations or trained model predictions.';}
    }
    document.getElementById('view-title').textContent=title;document.getElementById('view-description').textContent=description;
    document.getElementById('source-note').textContent=`Event: ${shortDate(inputs.event_datetime)} · Radar: ${shortDate(inputs.s1_post?.datetime)} · OSM: ${shortDate(inputs.osm_snapshot)} · Outside dated imagery: historical Sentinel-2 context (2025), not event evidence.`;
    let legend=before?swatch('#154a82','Pre-event water / rivers'):model?swatch('#1273d6',analysis.model_version==='b0'?'Baseline score · 0 → 1':analysis.model_version==='mock'?'Synthetic score · 0 → 1':'AI flood probability · 0 → 1'):swatch('#154a82','River / persistent water')+swatch('#0879bd','Flood · high')+swatch('#80c8e7','Flood · possible');
    if(step==='flow'&&flow?.features?.length)legend+=swatch('#1dc1db','Downstream DEM trace','line');
    if(!before&&!model&&step!=='access'&&floodPoints.features.length)legend+=swatch('#0879bd','Dot: small flood patch','dot');
    if(step==='access')legend+=swatch('#df493f','Inferred closure','line')+Object.entries(statusColors).map(([key,color])=>swatch(color,key.replaceAll('_',' '),'dot')).join('');
    if(extras.has('changes')&&!before)legend+=swatch('#cf930c','Radar decrease · water or mud')+swatch('#b23b27','Radar increase · roughness');
    if(extras.has('assets')&&!before)legend+=swatch('#e5a83a','Exposed road','line')+swatch('#eab566','Exposed building');
    if(extras.has('s2')&&!before)legend+=swatch('#25b5b3','Optical water · not all new flood');
    if(optical)legend+=swatch('#c3cbd0','Cloud / shadow / snow','hatch');
    if(extras.has('no_observation')&&!before)legend+=swatch('#727d85','Radar blind spot','hatch');
    document.getElementById('legend').innerHTML=legend;
    const next={before:'flood',flood:'flow',flow:'access',access:'before'}[step];
    const nextNames={before:'before',flood:'flood extent',flow:'downstream',access:'road access'};
    const nextButton=document.getElementById('next-step');nextButton.dataset.next=next;nextButton.innerHTML=`Next: ${nextNames[next]} <i data-lucide="arrow-right"></i>`;
    window.lucide?.createIcons({attrs:{'stroke-width':1.8,'aria-hidden':'true'}});
    updateLabels(map,labels);
    parent.postMessage({type:'cutoff-map-view',run,scenario,view:params.get('view'),step},location.origin);
  }
  window.addEventListener('message',event=>{
    const message=event.data;
    if(event.origin!==location.origin||event.source!==parent||message?.type!=='cutoff-focus-settlement'||message.run!==run||message.scenario!==scenario||String(message.view)!==params.get('view')||!Number.isFinite(message.lon)||!Number.isFinite(message.lat)||Math.abs(message.lon)>180||Math.abs(message.lat)>90)return;
    step='access';model=false;comparison=false;updateView();
    map.easeTo({center:[message.lon,message.lat],zoom:Math.max(map.getZoom(),14),duration:matchMedia('(prefers-reduced-motion: reduce)').matches?0:600});
    new maplibregl.Popup({maxWidth:'290px'}).setLngLat([message.lon,message.lat]).setHTML(popupHtml(message)).addTo(map);
  });
  map.on('load',()=>{
    for(const name of ['before_rgb','after_rgb','pre','post','before_water','permanent','flood','score','changes','s2','after_water','before_cloud','after_cloud','no_observation'])addRaster(map,name,false,['before_rgb','after_rgb','pre','post'].includes(name)?1:name.endsWith('_cloud')?.3:name==='score'?.85:.85);
    addContext(map,data.vectors.river_context);
    addGeo(map,'exposed-roads',data.vectors.exposed_roads,'line',{'line-color':'#e5a83a','line-width':2.4,'line-opacity':.8});
    addGeo(map,'exposed-buildings',data.vectors.exposed_buildings,'fill',{'fill-color':'#eab566','fill-opacity':.7});
    addGeo(map,'closed-casing',data.vectors.closed_roads,'line',{'line-color':'#fff4f0','line-width':4,'line-opacity':.8});
    addGeo(map,'closed-roads',data.vectors.closed_roads,'line',{'line-color':'#df493f','line-width':2.5,'line-opacity':.95});
    addGeo(map,'flow-base',flow,'line',{'line-color':'#123f55','line-width':5,'line-opacity':.9});
    addGeo(map,'flow-line',flow,'line',{'line-color':'#1dc1db','line-width':2.3,'line-opacity':.95});animateFlow(map,flow);
    addGeo(map,'settlements',data.vectors.settlements,'circle',{'circle-radius':['interpolate',['linear'],['zoom'],10,3.5,14,5,17,7],'circle-color':['match',['get','status'],...Object.entries(statusColors).flat(),'#9aabb7'],'circle-stroke-color':'#fff','circle-stroke-width':1.4});
    addGeo(map,'flood-detections',floodPoints,'circle',{'circle-radius':['interpolate',['linear'],['zoom'],10,4,13,3,15,0],'circle-color':['match',['get','class'],1,'#0879bd','#80c8e7'],'circle-stroke-color':'#fff','circle-stroke-width':1.2,'circle-opacity':.95});
    fitStudy();addLabels(map,labels);
    document.getElementById('model-title').textContent=analysis.model_version==='b0'?'B0 rule baseline':analysis.model_version==='mock'?'Synthetic demonstration':'U-Net v1 · trained flood model';
    document.getElementById('model-detail').textContent=`Decision threshold: ${analysis.hazard?.flood_threshold??'unavailable'} · Temperature: ${Number(analysis.hazard?.temperature||1).toFixed(3)}. Calibrated on global flood validation data; local terrain can differ.`;
    if(analysis.model_version==='b0'){
      document.getElementById('model-toggle').innerHTML='<i data-lucide="scan-line"></i>Baseline score';
      document.getElementById('model-explainer').textContent='This run uses the B0 radar rule baseline. Its three-class scores are rule outputs, not predictions from a trained U-Net.';
      document.getElementById('model-detail').textContent='B0 baseline · threshold '+(analysis.hazard?.flood_threshold??'unavailable')+'.';
    }
    if(analysis.model_version==='mock'){
      document.getElementById('model-explainer').textContent='Synthetic demonstration scores for product testing. These are not satellite observations or real model predictions.';
      document.getElementById('model-detail').textContent='Fictional test evidence.';
    }
    document.querySelectorAll('[data-layer]').forEach(button=>{
      const available=layerGroups[button.dataset.layer].some(id=>map.getLayer(id));button.disabled=!available;if(!available)extras.delete(button.dataset.layer);
      button.addEventListener('click',()=>{
        const name=button.dataset.layer;if(extras.has(name))extras.delete(name);else{extras.add(name);if(name==='pre')extras.delete('post');if(name==='post'){extras.delete('pre');step='flood';}}
        updateView();
      });
    });
    document.querySelectorAll('[data-step]').forEach(button=>button.addEventListener('click',()=>{step=button.dataset.step;model=false;if(step==='before')comparison=false;extras.delete('pre');extras.delete('post');document.querySelector('.layer-deck').open=false;updateView();}));
    document.getElementById('compare-toggle').addEventListener('click',()=>{comparison=!comparison;if(comparison&&step==='before')step='flood';document.querySelector('.layer-deck').open=false;updateView();});
    document.getElementById('model-toggle').disabled=!data.layers.score;
    document.getElementById('model-toggle').addEventListener('click',()=>{model=!model;if(model){step='flood';extras.delete('pre');extras.delete('post');extras.delete('changes');}document.querySelector('.layer-deck').open=false;updateView();});
    document.getElementById('reset-view').addEventListener('click',fitStudy);
    document.getElementById('inspect-flood').disabled=!floodPoints.features.length;
    document.getElementById('inspect-flood').addEventListener('click',()=>{
      step='flood';model=false;comparison=false;updateView();
      const point=floodPoints.features[0];map.easeTo({center:point.geometry.coordinates,zoom:15,duration:600});
      new maplibregl.Popup({maxWidth:'280px'}).setLngLat(point.geometry.coordinates).setHTML(popupHtml(point.properties)).addTo(map);
    });
    document.getElementById('trace-overview').addEventListener('click',()=>{
      const bounds=new maplibregl.LngLatBounds();for(const feature of flow.features){if(feature.geometry.type==='LineString')feature.geometry.coordinates.forEach(point=>bounds.extend(point));}
      if(!bounds.isEmpty())map.fitBounds(bounds,{padding:60,duration:600});
    });
    document.getElementById('divider').addEventListener('input',divider);
    document.getElementById('imagery-select').addEventListener('change',event=>{opticalMode=event.target.value;extras.delete('pre');extras.delete('post');if(opticalMode==='after'&&step==='before')step='flood';updateView();});
    document.getElementById('next-step').addEventListener('click',event=>{step=event.currentTarget.dataset.next;model=false;if(step==='before')comparison=false;updateView();});
    map.on('move',syncBefore);map.on('resize',()=>{if(beforeMap){beforeMap.resize();syncBefore();}});
    updateView();
    addHistoricalContext(map);
    const required=['before_rgb','after_rgb','pre','post','flood','permanent','no_observation'].filter(name=>data.layers[name]);
    let ready=false;
    function evidenceReady(){
      if(ready||!required.every(name=>map.isSourceLoaded(name)))return;
      ready=true;map.off('sourcedata',evidenceReady);
      requestAnimationFrame(()=>requestAnimationFrame(()=>{
        state.remove();parent.postMessage({type:'cutoff-map-ready',run,scenario,view:params.get('view')},location.origin);
      }));
    }
    map.on('sourcedata',evidenceReady);evidenceReady();
  });
  map.on('click',event=>{const features=map.queryRenderedFeatures(event.point,{layers:['flood-detections','settlements','closed-roads','exposed-roads','exposed-buildings','river-lines','river-areas'].filter(id=>map.getLayer(id))});if(features.length)new maplibregl.Popup({maxWidth:'300px'}).setLngLat(event.lngLat).setHTML(popupHtml(features[0].properties)).addTo(map)});
}
boot().catch(error=>{state.textContent=error.message;parent.postMessage({type:'cutoff-map-error',run,scenario,view:params.get('view')},location.origin)});
