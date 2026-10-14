const params=new URLSearchParams(location.search);
const run=params.get('run'),scenario=params.get('scenario')||'A';
const state=document.getElementById('map-state');
const statusColors={connected:'#f5f0eb',degraded:'#ff8a00',cut_off:'#ff1f0f',unknown:'#8c7a73'};
const layerGroups={hazard:['hazard','hazard-fill','hazard-edge','hazard-glow'],flow:['flow-base','flow-line','flow-particle-glow','flow-particles'],access:['closed-glow','closed-roads'],assets:['roads','exposed-roads','exposed-buildings','settlements-glow','settlements']};

function addGeo(map,id,data,type,paint,before){
  if(!data?.features?.length)return;
  map.addSource(id,{type:'geojson',data});
  map.addLayer({id,type,source:id,paint},before);
}
function popupHtml(properties){
  const title=properties.name||properties.highway||'Mapped feature';
  const fields=Object.entries(properties).filter(([k,v])=>v!==null&&v!==''&&['name','status','t0_min','t1_min','trail_access','class_name','closed'].includes(k));
  return `<strong>${String(title)}</strong>${fields.map(([k,v])=>`<p>${k.replace('_',' ')}: ${String(v)}</p>`).join('')}`;
}
function setupLayerControls(map){
  window.lucide?.createIcons({'stroke-width':1.8});
  document.querySelectorAll('[data-layer]').forEach(button=>button.addEventListener('click',()=>{
    button.classList.toggle('active');
    const visibility=button.classList.contains('active')?'visible':'none';
    layerGroups[button.dataset.layer].forEach(id=>{if(map.getLayer(id))map.setLayoutProperty(id,'visibility',visibility)});
  }));
}
function animateFlow(map,collection){
  const feature=collection?.features?.find(item=>item.geometry?.type==='LineString');
  const coordinates=feature?.geometry?.coordinates;
  if(!coordinates||coordinates.length<2)return;
  const particles={type:'FeatureCollection',features:[]};
  map.addSource('flow-particles',{type:'geojson',data:particles});
  map.addLayer({id:'flow-particle-glow',type:'circle',source:'flow-particles',paint:{'circle-radius':9,'circle-color':'#ff3d00','circle-opacity':.25,'circle-blur':.8}});
  map.addLayer({id:'flow-particles',type:'circle',source:'flow-particles',paint:{'circle-radius':3.5,'circle-color':'#ffe0b0','circle-stroke-color':'#ff4c00','circle-stroke-width':1.5}});
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
  const map=new maplibregl.Map({container:'map',center:[(w+e)/2,(s+n)/2],zoom:10,pitch:0,bearing:0,maxPitch:85,antialias:true,style:{version:8,sources:{satellite:{type:'raster',tiles:['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],tileSize:256,attribution:'Imagery © Esri and contributors'},terrain:{type:'raster-dem',tiles:['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],tileSize:256,encoding:'terrarium',maxzoom:15,attribution:'Elevation © AWS Terrain Tiles'},labels:{type:'raster',tiles:['https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'],tileSize:256}},layers:[{id:'satellite',type:'raster',source:'satellite'},{id:'terrain-shade',type:'hillshade',source:'terrain',paint:{'hillshade-shadow-color':'#140000','hillshade-highlight-color':'#ffb184','hillshade-accent-color':'#7d150d','hillshade-exaggeration':.35}}]}});
  window.cutoffMap=map;
  map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),'top-right');
  map.addControl(new maplibregl.FullscreenControl(),'top-right');
  map.addControl(new maplibregl.TerrainControl({source:'terrain',exaggeration:.65}),'top-right');
  map.on('load',()=>{
    map.setTerrain({source:'terrain',exaggeration:.65});
    map.addSource('hazard',{type:'image',url:data.hazard_url,coordinates:[[w,n],[e,n],[e,s],[w,s]]});
    map.addLayer({id:'hazard',type:'raster',source:'hazard',paint:{'raster-opacity':.3,'raster-fade-duration':600}});
    if(data.vectors.hazard_polygons?.features?.length){
      map.addSource('hazard-polygons',{type:'geojson',data:data.vectors.hazard_polygons});
      map.addLayer({id:'hazard-glow',type:'line',source:'hazard-polygons',paint:{'line-color':['match',['get','class'],1,'#0095ff',2,'#58d6ff',3,'#ff9a00',4,'#ff3b1c','#7b68ff'],'line-width':7,'line-blur':7,'line-opacity':.34}});
      map.addLayer({id:'hazard-fill',type:'fill',source:'hazard-polygons',paint:{'fill-color':['match',['get','class'],1,'#0077d9',2,'#66d9ff',3,'#ff9700',4,'#df2b16','#6655dd'],'fill-opacity':['match',['get','class'],1,.62,2,.42,3,.42,4,.58,.35]}});
      map.addLayer({id:'hazard-edge',type:'line',source:'hazard-polygons',paint:{'line-color':['match',['get','class'],1,'#5dc8ff',2,'#b5ecff',3,'#ffd061',4,'#ff7358','#aca3ff'],'line-width':1.1,'line-opacity':.82}});
    }
    addGeo(map,'roads',data.vectors.roads,'line',{'line-color':'#f4d1bf','line-width':['interpolate',['linear'],['zoom'],10,.3,15,1.5],'line-opacity':.34});
    addGeo(map,'exposed-roads',data.vectors.exposed_roads,'line',{'line-color':'#ff8a00','line-width':4,'line-opacity':.9});
    addGeo(map,'exposed-buildings',data.vectors.exposed_buildings,'fill-extrusion',{'fill-extrusion-color':'#b80000','fill-extrusion-height':20,'fill-extrusion-base':1,'fill-extrusion-opacity':.78});
    addGeo(map,'closed-glow',data.vectors.closed_roads,'line',{'line-color':'#ff230f','line-width':10,'line-blur':8,'line-opacity':.7});
    addGeo(map,'closed-roads',data.vectors.closed_roads,'line',{'line-color':'#ff351d','line-width':4,'line-opacity':1});
    const flow=data.vectors.flowpath||data.vectors.derived_flow;
    addGeo(map,'flow-base',flow,'line',{'line-color':'#2a0902','line-width':11,'line-opacity':.7});
    addGeo(map,'flow-line',flow,'line',{'line-color':'#ff7a00','line-width':3,'line-opacity':.95,'line-dasharray':[2,1.2]});
    animateFlow(map,flow);
    if(data.vectors.settlements?.features?.length){map.addSource('settlements',{type:'geojson',data:data.vectors.settlements});map.addLayer({id:'settlements-glow',type:'circle',source:'settlements',paint:{'circle-radius':12,'circle-color':['match',['get','status'],...Object.entries(statusColors).flat(),'#fff'],'circle-opacity':.2,'circle-blur':.8}});map.addLayer({id:'settlements',type:'circle',source:'settlements',paint:{'circle-radius':6,'circle-color':['match',['get','status'],...Object.entries(statusColors).flat(),'#fff'],'circle-stroke-color':'#140604','circle-stroke-width':2}})}
    map.addLayer({id:'labels',type:'raster',source:'labels',paint:{'raster-opacity':.82}});
    setupLayerControls(map);
    map.fitBounds([[w,s],[e,n]],{padding:55,duration:0});
    setTimeout(()=>map.easeTo({pitch:42,bearing:-18,zoom:map.getZoom()-.45,duration:2600,easing:t=>1-Math.pow(1-t,4)}),350);
    state.style.opacity='0';setTimeout(()=>state.remove(),500);
  });
  map.on('click',event=>{const features=map.queryRenderedFeatures(event.point,{layers:['settlements','closed-roads','exposed-roads','exposed-buildings'].filter(id=>map.getLayer(id))});if(features.length)new maplibregl.Popup({closeButton:true,maxWidth:'270px'}).setLngLat(event.lngLat).setHTML(popupHtml(features[0].properties)).addTo(map)});
  map.on('mouseenter','settlements',()=>map.getCanvas().style.cursor='pointer');map.on('mouseleave','settlements',()=>map.getCanvas().style.cursor='');
}
boot().catch(error=>{state.textContent=error.message;state.style.color='#ff6a52'});
