ENV          := riprap
TRITON_REPO  ?= ../riprap-triton
FRONTEND_URL := https://msradam-riprap--riprap-frontend-web-app.modal.run
PROXY_URL    := https://msradam-riprap--riprap-triton-riprap-proxy.modal.run
Q            ?= flood risk at 1 Wall Street, Manhattan

.DEFAULT_GOAL := help
.PHONY: help up up-gpu up-frontend down status warm query dashboard-gpu dashboard-frontend logs-gpu logs-frontend

help:  ## list targets
	@grep -hE '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sort | \
	  awk -F':.*##' '{printf "  \033[36m%-14s\033[0m%s\n", $$1, $$2}'

up: up-gpu up-frontend  ## deploy both apps (scale-to-zero; $0 idle)

up-gpu:  ## deploy the Triton + vLLM GPU app (from $(TRITON_REPO))
	cd $(TRITON_REPO) && modal deploy modal/riprap_modal.py --env $(ENV)

up-frontend:  ## deploy the FastAPI + SvelteKit CPU app
	modal deploy modal/riprap_frontend.py --env $(ENV)

down:  ## fully stop (undeploy) both apps; idle is already $0 without this
	-modal app stop riprap-frontend --env $(ENV) --yes
	-modal app stop riprap-triton   --env $(ENV) --yes

status:  ## list apps + running tasks
	modal app list --env $(ENV)

dashboard-gpu:  ## open the GPU app on the Modal web dashboard
	modal app dashboard riprap-triton --env $(ENV)

dashboard-frontend:  ## open the frontend app on the Modal web dashboard
	modal app dashboard riprap-frontend --env $(ENV)

warm:  ## wake the GPU and block until vLLM is ready (needs RIPRAP_PROXY_TOKEN)
	@PROXY_URL=$(PROXY_URL) bash modal/warm.sh

query:  ## one end-to-end query (override with Q="...")
	@curl -sN -G "$(FRONTEND_URL)/api/agent/stream" --data-urlencode "q=$(Q)" \
	  | grep -E '^event: (plan|final|done)' || true

logs-gpu:  ## tail GPU app logs
	modal app logs riprap-triton --env $(ENV)

logs-frontend:  ## tail frontend app logs
	modal app logs riprap-frontend --env $(ENV)
