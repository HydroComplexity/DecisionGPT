docker stack rm decisiongpt
docker network create --driver overlay decisiongpt_gptnet

# docker service rm $(docker ps --format "table {{.ID}}\t{{.Names}}" | grep add_agent | awk '{split($2, a, "."); print a[1]}')

docker service rm $(docker service ls --format 'table {{.ID}}\t{{.Name}}' | grep add_agent | awk '{print $1}')