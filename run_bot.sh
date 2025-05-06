#!/bin/bash

if [ ! -d "venv" ]; then
    ./setup_env.sh
fi

source venv/bin/activate
python3 run_bot.py "$@"
deactivate