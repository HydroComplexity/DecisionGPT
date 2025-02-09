docker pull python:3.11.4-bookworm
docker run -ti --name python_build -v ./requirements.txt:/requirements.txt python:3.11.4-bookworm pip install -r requirements.txt
docker commit python_build python_gpt
docker stop python_build && docker rm python_build