FROM node:20-slim

WORKDIR /workspace/apps/ui

COPY apps/ui/package.json apps/ui/package-lock.json ./
RUN npm ci

COPY apps/ui/ ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
