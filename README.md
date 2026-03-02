# DecisionGPT

This framework implements a multi-agent LLM for decision-making discourse running on Google ADK, and using docker compose to structure the frontend, backend and intra-process communication.

### Requirements

- Docker

### Setup

The decisiongpt_backend image needs to be built in order to run the framework. While in the decisiongpt directory, execute:


```bash
# in the decisiongpt folder
# this is important to run this command in the src/frontend directory directly, otherwise docker build won't be able to find requirements.txt
docker build -t decisiongpt_backend .

```

Fill in OpenAI API credentials in .env
Example:

```
OPENAI_API_KEY=abcdef1234567890
OPENAI_API_ENDPOINT=https:/openaiapi.com/myapiendpoint
OPENAI_API_DEPLOYMENT_NAME=gpt4-turbo-uofi-urbana-champaign

We are using OpenAI API through Microsoft Azure Cloud.
If you use the OpenAI API through OpenAI, code has to be changed in src/macro/conference_room.py and src/micro/agent.py:

# current code:

from openai import AzureOpenAI

[...]

self.client = openai.AzureOpenAI(

[...]

# modify to:
from openai import OpenAI

[...]

self.client = openai.OpenAI(

[...]



```

### Execution

```bash
# start the swarm service

sh start_swarm.sh

# run the framework

sh deploy_swarm.sh

# agent logs and conference_room logs are recorded in out/logs/
# container real time output can be viewed with

docker service logs -f --tail 100 decisiongpt_conference_room
docker service logs -f --tail 100 decisiongpt_agent1
docker service logs -f --tail 100 decisiongpt_agent2
...

# In a web browser, browse to localhost:8080 to display the GUI,
# once ./deploy_swarm.sh has been executed.

# Stop the framework with

sh retreat_swarm.sh

# Once you want to stop running the framework, disable swarm mode
# with

sh stop_swarm.sh
```