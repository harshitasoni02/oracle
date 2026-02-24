FROM node:20-alpine

WORKDIR /app

RUN mkdir -p /app

COPY package*.json ./
RUN npm install --ignore-scripts || true

COPY . .

EXPOSE 80

CMD ["npm", "run", "dev"]
