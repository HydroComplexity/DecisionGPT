mkdir -p out/logs/agent_logs
mkdir -p out/logs/cr_logs
mkdir -p out/logs/keep
docker stack deploy --compose-file composev3.yaml decisiongpt
