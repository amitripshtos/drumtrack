FROM node:22-alpine AS base

RUN corepack enable && corepack prepare pnpm@9 --activate

WORKDIR /app

# Install dependencies first (better layer caching)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source and config files
COPY app/ app/
COPY components/ components/
COPY hooks/ hooks/
COPY lib/ lib/
COPY types/ types/
COPY public/ public/
COPY tsconfig.json next.config.ts postcss.config.mjs components.json ./

# Build — NEXT_PUBLIC_API_URL is baked in at build time.
# For local docker-compose, the browser talks to localhost:8000 directly.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm build

# --- Production stage ---
FROM node:22-alpine AS production

RUN corepack enable && corepack prepare pnpm@9 --activate

WORKDIR /app

COPY --from=base /app/package.json /app/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --prod

COPY --from=base /app/.next ./.next
COPY --from=base /app/public ./public

EXPOSE 3000

CMD ["pnpm", "start"]
