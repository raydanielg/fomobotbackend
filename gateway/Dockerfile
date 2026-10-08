FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev && npm cache clean --force

COPY src/ src/

RUN adduser -D -u 10001 fomobot && mkdir -p /data/sessions && chown -R fomobot /app /data
USER fomobot

ENV PORT=4000
EXPOSE 4000

CMD ["node", "src/index.js"]
