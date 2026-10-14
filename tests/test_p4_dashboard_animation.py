"""Exercise the actual map animation with browser frame timestamp ordering."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="JavaScript runtime not installed")
def test_flow_animation_handles_first_frame_earlier_than_initialization():
    source = Path(__file__).resolve().parents[1] / "app/static/map.js"
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[1],'utf8');
const animate=source.slice(source.indexOf('function animateFlow('),source.indexOf('async function boot('));
const callbacks=[],sources={};
const context={performance:{now:()=>100},requestAnimationFrame:cb=>callbacks.push(cb)};
vm.createContext(context);vm.runInContext(animate,context);
const map={addSource:(id,value)=>sources[id]={setData:data=>sources[id].data=data},
           addLayer:()=>{},getSource:id=>sources[id]};
context.animateFlow(map,{features:[{geometry:{type:'LineString',coordinates:[[0,0],[10,20]]}}]});
for(const time of [90,100,6500,6600]){
  callbacks.shift()(time);
  const data=sources['flow-particles'].data;
  assert(data.features.length>0);
  for(const feature of data.features){
    const [x,y]=feature.geometry.coordinates;
    assert(Number.isFinite(x)&&Number.isFinite(y));
    assert(x>=0&&x<=10&&y>=0&&y<=20);
  }
}
"""
    subprocess.run([shutil.which("node"), "-e", script, str(source)], check=True, capture_output=True, text=True)
