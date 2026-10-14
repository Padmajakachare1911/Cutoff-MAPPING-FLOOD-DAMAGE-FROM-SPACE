"""Cutoff product: Results statistics plus contract map layers."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from cutoff.contracts import (
    ATTRIBUTION,
    DEFAULT_OSM_SNAPSHOT,
    DISCLAIMER,
    HAZARD_CLASS_NAMES,
    Flag,
)
from cutoff.report.schema import Results

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from map_layers import build_map  # noqa: E402


@st.cache_data(show_spinner=False)
def read_results(path, modified):
    return Results.model_validate_json(Path(path).read_text(encoding='utf-8'))


def tail_log(root):
    path = root / 'run.log'
    if path.is_file():
        return path.read_text(encoding='utf-8').splitlines()[-20:]
    return []


def launch(bbox, event, mode, model, snapshot, output, cache_dir):
    run_id = f'{datetime.now(UTC):%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:8]}'
    command = [sys.executable, '-m', 'cutoff.cli', 'run', '--bbox', bbox, '--event', event,
               '--mode', mode, '--model', model, '--osm-snapshot', snapshot,
               '--out', str(output), '--run-id', run_id, '--cache-dir', cache_dir]
    root = output / run_id
    output.mkdir(parents=True, exist_ok=True)
    console = output / f'{run_id}.console.log'
    with console.open('w', encoding='utf-8') as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    st.session_state['active_process'] = process
    st.session_state['active_root'] = str(root)
    st.session_state['active_console'] = str(console)
    return root


def progress():
    process = st.session_state.get('active_process')
    if process is None:
        return
    root = Path(st.session_state['active_root'])
    lines = tail_log(root)
    last = json.loads(lines[-1]) if lines else {}
    if process.poll() is None:
        with st.spinner(f"Running {last.get('stage', 'initialization')}..."):
            st.caption('Stage progress refreshes automatically. Acquisition can take several minutes.')
            st.code('\n'.join(lines[-6:]), language='json')
    else:
        if process.returncode == 0:
            st.success(f'Run finished: {root.name}')
        else:
            st.error(Path(st.session_state['active_console']).read_text(encoding='utf-8')[-2500:])
        del st.session_state['active_process']
        st.session_state['run_history'] = str(root)
        st.rerun()


def inspect_click(root, clicked):
    if not clicked or not (root / 'flags.tif').is_file():
        return
    import rasterio
    from pyproj import Transformer
    with rasterio.open(root / 'flags.tif') as flags, rasterio.open(root / 'hazard_class.tif') as hazard:
        x, y = Transformer.from_crs(4326, flags.crs, always_xy=True).transform(clicked['lng'], clicked['lat'])
        row, col = flags.index(x, y)
        if 0 <= row < flags.height and 0 <= col < flags.width:
            bits = int(flags.read(1, window=((row, row+1), (col, col+1)))[0, 0])
            code = int(hazard.read(1, window=((row, row+1), (col, col+1)))[0, 0])
            reasons = [flag.name.lower().replace('_', ' ') for flag in Flag if bits & int(flag)]
            st.info('Pixel evidence: ' + HAZARD_CLASS_NAMES[code].replace('_', ' ') +
                    '. Reasons: ' + (', '.join(reasons) or 'no evidence flags'))


def main():
    st.set_page_config(page_title='Cutoff | Flood exposure and access', layout='wide')
    output = Path(os.environ.get('CUTOFF_OUTPUT_DIR', str(ROOT / 'outputs'))).resolve()
    st.title('Cutoff')
    st.caption('Where did it hit? What was exposed? Who may be cut off?')
    st.warning(DISCLAIMER)
    with st.sidebar:
        st.header('New analysis')
        bbox = st.text_input('AOI bbox W,S,E,N', '85.28,28.10,85.42,28.29')
        event = st.text_input('Event datetime (UTC)', '2026-08-26T02:52:00Z')
        st.text_input('Default OSM snapshot', DEFAULT_OSM_SNAPSHOT, disabled=True)
        snapshot = st.text_input('Pre-event OSM override', DEFAULT_OSM_SNAPSHOT,
                                 help='For an earlier event, choose a snapshot strictly before it.')
        mode = st.selectbox('Mode', ['cached', 'fast', 'full'])
        selection = st.selectbox('Model', ['Checkpoint', 'b0'])
        checkpoint = st.text_input('Checkpoint path', str(ROOT / 'models' / 'cutoff_unet_v1.pt'))
        cache = st.text_input('Cache directory', os.environ.get('CUTOFF_CACHE_DIR', str(ROOT / 'cache')))
        active = st.session_state.get('active_process') is not None
        if st.button('Run', type='primary', disabled=active):
            from cutoff.cli import coordinates
            from cutoff.pipeline import parse_event
            try:
                coordinates(bbox)
                dt, _ = parse_event(event)
                sd, _ = parse_event(snapshot)
                if sd >= dt:
                    raise ValueError('OSM snapshot must be strictly before the event')
                model = checkpoint if selection == 'Checkpoint' else 'b0'
                if model != 'b0' and not Path(model).is_file():
                    raise ValueError('Download model-v1 or choose b0.')
                launch(bbox, event, mode, model, snapshot, output, cache)
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        history = sorted([p for p in output.glob('*') if p.is_dir() and
                          ((p / 'results.json').exists() or (p / 'error.json').exists())],
                         key=lambda p: p.stat().st_mtime, reverse=True)
        chosen = st.selectbox('Run history', [str(p) for p in history],
                              format_func=lambda path: Path(path).name, key='run_history') if history else None
        scenario = st.radio('Scenario', ['A', 'B', 'C'], horizontal=True)
        st.caption(DISCLAIMER)
    if hasattr(st, 'fragment'):
        st.fragment(run_every='1s')(progress)()
    else:
        progress()
    if not chosen:
        st.info('No runs yet. Generate the synthetic demo with cutoff mock, or start an analysis.')
        return
    root = Path(chosen)
    if not (root / 'results.json').is_file():
        error = json.loads((root / 'error.json').read_text(encoding='utf-8'))
        st.error(('No valid same-track pair\n\n' if error['error_type'] == 'NoValidPair' else 'Run failed\n\n')
                 + error['message'])
        return
    results = read_results(str(root / 'results.json'), (root / 'results.json').stat().st_mtime_ns)
    if results.model_version == 'mock':
        st.info('SYNTHETIC DEMONSTRATION - fictional data for product testing.')
    if results.exposure is None or not results.access:
        st.warning('Partial run - exposure or road access is unavailable. Hazard evidence remains available.')
    for warning in results.warnings:
        st.warning(warning)
    inputs = results.inputs.model_dump(mode='json')
    with st.expander('Inputs and provenance'):
        st.json(inputs)
    frozen_file = ROOT / 'docs' / 'results' / 'frozen_runs.txt'
    frozen = set(frozen_file.read_text(encoding='utf-8').splitlines()) if frozen_file.is_file() else set()
    names = ['Map and situation', 'Downloads'] + (['Evaluation'] if results.run_id in frozen else [])
    tabs = st.tabs(names)
    with tabs[0]:
        map_column, panel = st.columns([2, 1])
        with panel:
            st.subheader('Where - hazard area (km²)')
            st.dataframe([{'class': name, 'km²': value} for name, value in results.hazard.area_km2_by_class.items()],
                         hide_index=True, use_container_width=True)
            st.metric('No observation (km²)', results.hazard.no_observation_km2)
            st.subheader('What - exposure')
            if results.exposure is None:
                st.caption('Unavailable for this partial run.')
            else:
                st.dataframe([{'class': name, 'buildings': count,
                    'road km': results.exposure.road_km_by_class.get(name),
                    'bridges': results.exposure.bridges_by_class.get(name)}
                    for name, count in results.exposure.buildings_by_class.items()], hide_index=True)
            st.subheader(f'Who - scenario {scenario}')
            current = next((s for s in results.access if s.scenario == scenario), None)
            if current:
                st.caption(current.description)
                for label, key in [('Connected', 'connected'), ('Degraded', 'degraded'),
                                   ('Cut off', 'cut_off'), ('Unknown', 'unknown')]:
                    st.metric(label, current.counts.get(key))
                st.metric('Closed road km', current.closed_road_km)
                st.metric('Closed bridges', current.closed_bridges)
                st.write('Cut off:', ', '.join(v.name for v in current.cut_off) or 'none')
                st.caption('Unknown means no mapped baseline route, not safe. Trail access appears in popups.')
        with map_column:
            from streamlit_folium import st_folium
            try:
                rendered = st_folium(build_map(results, root, scenario), height=640, use_container_width=True,
                                     returned_objects=['last_clicked'], key=f'map_{root.name}_{scenario}')
                inspect_click(root, rendered.get('last_clicked') if rendered else None)
            except (ValueError, OSError) as exc:
                st.error(f'Map layer unavailable: {exc}')
        with st.expander('Limitations'):
            for limitation in results.limitations:
                st.write(limitation)
    with tabs[1]:
        for label, filename, mime in [
            ('Situation report PDF', 'sitrep.pdf', 'application/pdf'),
            ('Hazard GeoPackage', 'hazard.gpkg', 'application/geopackage+sqlite3'),
            (f'Settlements {scenario}', f'settlements_{scenario}.gpkg', 'application/geopackage+sqlite3'),
            ('Hazard GeoTIFF', 'hazard_class.tif', 'image/tiff'),
            ('Results JSON', 'results.json', 'application/json'),
        ]:
            path = root / filename
            if path.is_file():
                st.download_button(label, path.read_bytes(), file_name=filename, mime=mime)
        st.caption('OSM-derived exports: ODbL 1.0 - © OpenStreetMap contributors.')
    if len(tabs) == 3:
        with tabs[2]:
            st.caption('Check-only evidence from frozen runs. No reference product is a pipeline input.')
            for name in ('P2_kuro_results.md', 'E4.md', 'E6.md'):
                path = ROOT / 'docs' / 'results' / name
                if path.is_file():
                    st.markdown(path.read_text(encoding='utf-8'))
    for credit in ATTRIBUTION:
        st.caption(credit)


if __name__ == '__main__':
    main()
