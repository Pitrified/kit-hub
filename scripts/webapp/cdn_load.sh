#!/bin/bash

# Load project-specific resources from CDN to local static folder.
# Vendor assets (Bulma, HTMX, Swagger UI, ReDoc) are now bundled inside
# fastapi-tools and served automatically at /vendor/ - no download needed.
# References in docs: docs/guides/webapp_setup.md

mkdir -p static/css static/img

echo "Static directories created. Vendor assets (Bulma, HTMX, Swagger) are served from fastapi-tools at /vendor/."
