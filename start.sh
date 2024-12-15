#!/bin/bash
if [ "$ENV" = "production" ]; then
    uvicorn main:app --host 0.0.0.0 --port $PORT
else
    uvicorn main:app --host 0.0.0.0 --port 8080 --reload
fi
