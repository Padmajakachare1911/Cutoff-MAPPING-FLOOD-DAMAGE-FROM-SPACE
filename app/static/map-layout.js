// Keep the canvas height stable when explanatory rows or layer controls expand.
const layoutParams=new URLSearchParams(location.search);
const mapChrome=new ResizeObserver(()=>{
  const rows=document.querySelectorAll('.story-toolbar,.scene-metadata,.legend,.comparison-controls,.interpretation,#model-card');
  const chromeHeight=Math.ceil([...rows].reduce((height,row)=>height+row.getBoundingClientRect().height,0));
  parent.postMessage({type:'cutoff-map-height',run:layoutParams.get('run'),scenario:layoutParams.get('scenario')||'A',view:layoutParams.get('view'),chromeHeight},location.origin);
});
document.querySelectorAll('.story-toolbar,.scene-metadata,.legend,.comparison-controls,.interpretation,#model-card').forEach(row=>mapChrome.observe(row));
