docker swarm init --advertise-addr 127.0.0.1

docker service create --restart-condition=none --name registry --publish published=5000,target=5000 registry:2

docker network create --driver overlay gptnet