# thedecade_2026nakshatra
Satellite-based flood mapping and impact assessment using Sentinel-1 SAR imagery to identify inundated areas and estimate potential impacts on roads, buildings, and settlements in Nepal's Terai region.

# Guardian of the Terai 
### Satellite-Based Flood Mapping & Impact Assessment

**Guardian of the Terai (तराई प्रहरी)** is a geospatial flood-mapping project designed to identify potentially inundated areas using Sentinel-1 Synthetic Aperture Radar (SAR) imagery and assess nearby infrastructure exposure.

Our goal is to turn satellite observations into actionable insights that support flood assessment and disaster-response planning in Nepal's Terai region.

 The Problem

Floods can spread rapidly, making it difficult for response teams to determine the affected areas and identify nearby communities and infrastructure that may need attention. Cloud cover can also limit the use of conventional optical satellite imagery.

 Our Solution

Guardian of the Terai compares pre-flood and post-flood radar imagery to detect changes that may indicate inundation. The results can be visualized on an interactive dashboard alongside available geographic information about roads, buildings, and settlements.

 How It Works

1. **Satellite Data:** Provide pre-flood and post-flood GeoTIFF imagery.
2. **Preprocessing:** Prepare the raster data for comparison.
3. **Flood Detection:** Analyze radar backscatter changes to identify potentially flooded areas.
4. **Impact Assessment:** Compare detected flood extent with available infrastructure and settlement data.
5. **Visualization:** Explore flood maps and available statistics through the dashboard.
6. **Export:** Access generated geospatial outputs supported by the application.

 System Architecture

```text
Satellite Images (GeoTIFF)
          ↓
     FastAPI Backend
          ↓
   Raster Preprocessing
          ↓
     Flood Detection
          ↓
   Flood Extent Outputs
          ↓
  Geospatial Impact Analysis
          ↓
   Streamlit Dashboard
          ↓
 Maps, Statistics & Results
```

 Tech Stack

- **Language:** Python
- **Backend:** FastAPI, Uvicorn
- **Geospatial Processing:** Rasterio, NumPy, Shapely, Fiona
- **Dashboard:** Streamlit, Folium
- **Data Formats:** GeoTIFF, GeoJSON
- **Testing:** pytest

 Run Locally

### Prerequisites
- Python 3.11
- Conda/Miniforge recommended for geospatial dependencies
- Git

### 1. Clone the repository

```bash
git clone https://github.com/sristi991-sys/thedecade_2026nakshatra.git
cd thedecade_2026nakshatra
```

### 2. Install dependencies

If `requirements.txt` exists:

```bash
python -m pip install -r requirements.txt
```

Otherwise, if dependencies are configured in `pyproject.toml`:

```bash
python -m pip install -e .
```

### 3. Start the backend

```bash
python -m uvicorn guardian.api.main:app --host 127.0.0.1 --port 8000
```

Health check: `http://127.0.0.1:8000/health`

### 4. Start the dashboard

Open a second terminal:

```bash
python -m streamlit run dashboard/app.py --server.port 8501
```

Dashboard: `http://localhost:8501`

 Project Structure

```text
├── dashboard/    # Streamlit interface
├── guardian/     # Backend and geospatial processing
├── data/         # Input and demo data
├── scripts/      # Utility scripts
├── tests/        # Automated tests
├── pyproject.toml
└── README.md
```

 Potential Applications

- Flood extent mapping
- Preliminary infrastructure exposure assessment
- Identification of areas requiring field verification
- Disaster-response planning and prioritization
- Geospatial analysis for researchers and response teams

 Limitations

Flood detection depends on suitable imagery, preprocessing, and detection thresholds. Radar changes can occur for reasons other than flooding. Infrastructure exposure estimates do not confirm actual damage and should be verified with reliable reference data or field observations.

 Future Scope

- Automated Sentinel-1 data acquisition
- Improved flood classification and validation
- Time-series flood monitoring
- More detailed infrastructure impact analysis
- Enhanced map exports and reporting

*Turning satellite observations into actionable flood intelligence.*

