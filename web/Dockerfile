# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim
WORKDIR /app
COPY package*.json ./
RUN --mount=type=secret,id=proxy_ca,target=/run/secrets/proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --strict-ssl=true --no-audit --no-fund --fetch-retries=1 --fetch-timeout=30000
COPY --chown=node:node . .
ENV NEXT_TELEMETRY_DISABLED=1
ARG API_URL=http://api:8000
ENV API_URL=$API_URL
RUN npm run build
USER node
CMD ["npm","start"]
