FROM node:25-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force
COPY dist ./dist
EXPOSE 3000
CMD ["npm", "run", "start:prod"]
