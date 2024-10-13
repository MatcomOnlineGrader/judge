#!/usr/bin/env bash
docker ps -q --filter "name=judge_api" | xargs -r docker restart
docker ps -q --filter "name=judge_grader" | xargs -r docker restart
