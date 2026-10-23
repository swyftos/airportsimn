#!/usr/bin/env bash
set -e

# Change to project root directory
cd "$(dirname "$0")"

# 1. Create .venv if missing
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    if command -v python3 >/dev/null 2>&1; then
        python3 -m venv .venv
    else
        python -m venv .venv
    fi
fi

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
elif [ -f ".venv/Scripts/activate" ]; then
    source ".venv/Scripts/activate"
fi

# 2. Install dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# 3. Generate synthetic data if missing
if [ ! -f "data/event_hourly.csv" ]; then
    echo "data/event_hourly.csv not found. Running data/generate.py..."
    python data/generate.py
fi

# 4. Launch Streamlit application
echo "Starting Streamlit application..."
streamlit run app/streamlit_app.py "$@"
