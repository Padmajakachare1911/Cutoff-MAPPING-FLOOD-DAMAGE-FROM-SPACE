# P4 fresh installation evidence

14 October 2026: built a wheel from the checkout, created a separate Python 3.12.14
virtual environment **without system site packages**, and installed the wheel with
dev/app/pdf extras. Executed from an empty sandbox outside the source working
directory; import path confirmed the fresh environment's site-packages.

Commands:

```text
python -m pip wheel . --no-deps --wheel-dir outputs/wheels
<Python 3.12> -m venv outputs/fresh-venv
outputs/fresh-venv/Scripts/python -m pip install outputs/wheels/cutoff-0.1.0-py3-none-any.whl[dev,app,pdf]
<fresh python> <absolute path>/outputs/check_install.py
```

Result: **FRESH WHEEL: config, templates, contracts, one-page PDF passed**.
The wheel contains the default YAML and sitrep template; no source-folder import
was needed. Native WeasyPrint was unavailable on Windows; xhtml2pdf succeeded.

This is agent-executed isolation testing, not the plan's independent teammate
rehearsal. That human fresh-clone/rehearsal check remains explicit in submission.md.
Live acquisition still requires the relevant personal API credentials and source
caches. The model release was downloaded and checksum verified separately.
