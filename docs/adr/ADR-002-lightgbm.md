# ADR 002: LightGBM for Localized Stadium Occupancy Forecasting

## Context and Problem Statement
On match days, crowd density fluctuates rapidly. We need a machine learning model capable of forecasting occupancy levels per zone 15-30 minutes into the future. The inference loop must execute in under 30 milliseconds locally, and run on lightweight infrastructure (like Render CPU instances) without requiring GPU acceleration.

## Decision Drivers
* **Inference Latency**: Predict in under 30 ms to prevent event ingestion delays.
* **Feature Set**: Tabular time-series data (historical counts, lag variables, match events).
* **Resource Profile**: Minimal memory usage, runs on standard CPU.
* **Accuracy**: High precision to avoid false positives in crowd safety alerts.

## Considered Options
1. **LSTM / RNN (PyTorch)**
2. **Prophet (Meta)**
3. **LightGBM (Light Gradient Boosting Machine)**

## Decision Outcome
Chosen Option: **LightGBM**

### Rationale
* **Execution Speed**: Lightweight trees execute in `< 10ms` on CPU.
* **Data Type Fit**: Excels at tabular dataset features containing lag occupancy metrics and temporal indexes.
* **Dependency Size**: PyTorch wheel is over 700MB, whereas LightGBM is under 5MB, making docker builds fast and keeping package size compact.

## Pros and Cons of Chosen Option

### Pros
* Extremely fast inference (averages 1.5ms).
* High accuracy with minimal training parameters.
* Small package footprint.

### Cons
* Cannot natively learn spatial relationships without explicit feature engineering. We resolved this by including neighboring zone density features in training datasets.
