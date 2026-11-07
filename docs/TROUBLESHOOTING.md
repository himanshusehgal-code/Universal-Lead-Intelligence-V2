# Troubleshooting

| Symptom | Likely reason | Action |
|---|---|---|
| `Map all five parameters` | A required standard feature is unmapped | Map all five required columns |
| `Mapped column does not exist` | Mapping spelling differs from CSV header | Copy the exact header from preview |
| `No trained model found` | Training has not completed or model disk is missing | Train first; check `MODEL_DIR` and persistent disk |
| No conversion probability | Outcome column absent, labels unrecognized or too few examples | Normalize Converted/Lost labels and check class counts |
| `Could not read CSV` | Invalid CSV encoding/format or malformed file | Save as UTF-8 CSV and retry |
| Unexpected categories | Source labels are inconsistent | Normalize category names before training |
| Render loses model after restart | Model directory is not on persistent disk | Verify disk mount and `MODEL_DIR` |
| Slow upload/training | Large CSV and synchronous request processing | Use smaller test data; V2 should use background jobs |

For API error details, inspect the JSON `detail` field and Render application logs.
