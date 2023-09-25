#!/bin/bash
# Env vars should be set in container spec
python run.py $BENCHMARK_NAME -t $BENCHMARK_TYPE -d $BENCHMARK_DEVICE --bs $INPUT_DATA_BATCH_SIZE