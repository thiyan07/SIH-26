"""Erode District bulk expansion pipeline.

Modules
-------
geographic_index : village/town geographic index (geocoded census + LGD blocks)
discovery        : systematic per-village multi-category business discovery
coverage         : coverage metrics + reports

Run the whole pipeline with::

    python -m scripts.erode.run_pipeline --run-discovery

The pipeline is resumable: geocoding and per-village discovery progress are
cached on disk under ``data/erode/{cache_dir}`` so interrupted runs resume.
"""