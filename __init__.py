"""Guardian of the Terai — Satellite-based flood mapping for Nepal's Terai region.

This package provides tools for detecting flooded areas by comparing
pre-flood and post-flood Sentinel-1 SAR backscatter GeoTIFFs.

Sub-packages
------------
preprocessing
    Sentinel-1 GeoTIFF validation and loading.
detection
    Flood detection via backscatter change thresholding.
output
    Writing flood masks as GeoTIFF and GeoJSON.
api
    FastAPI application exposing detection as a REST service.
"""
